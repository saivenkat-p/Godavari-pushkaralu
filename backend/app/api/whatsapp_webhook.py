import logging
from fastapi import APIRouter, Request, Query, Response, status, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import verify_meta_webhook_signature
from backend.app.services.whatsapp_service import WhatsAppService
from backend.app.services.conversation_engine import ConversationEngine

logger = logging.getLogger("whatsapp_webhook")
router = APIRouter(prefix="/api/webhook/whatsapp", tags=["WhatsApp Webhook"])


@router.get("")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """
    Official Meta WhatsApp Webhook verification endpoint.
    Meta sends a GET request with hub.mode, hub.verify_token, and hub.challenge.
    """
    logger.info(f"Received webhook verification request: mode={hub_mode}, token={hub_verify_token}")
    
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verification SUCCESSFUL. Responding with challenge.")
        return Response(content=hub_challenge, media_type="text/plain", status_code=200)
    
    logger.warning("Webhook verification FAILED. Tokens do not match.")
    return Response(content="Forbidden", status_code=status.HTTP_403_FORBIDDEN)


@router.post("")
async def receive_webhook_payload(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256")
):
    """
    Official Meta WhatsApp Webhook inbound message processor.
    Validates HMAC-SHA256 signature, deduplicates messages, processes state machine,
    and dispatches automated responses.
    """
    raw_body = await request.body()

    # Validate HMAC signature if secret is configured
    if not verify_meta_webhook_signature(raw_body, x_hub_signature_256):
        logger.warning("Invalid Meta Webhook Signature rejected.")
        return Response(content="Invalid Signature", status_code=status.HTTP_403_FORBIDDEN)

    try:
        payload = await request.json()
    except Exception:
        return Response(content="Bad Request", status_code=status.HTTP_400_BAD_REQUEST)

    # Check for Meta message object structure
    entries = payload.get("entry", [])
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                message_id = msg.get("id")
                from_phone = msg.get("from")
                msg_type = msg.get("type")

                # Deduplication / Retry protection
                if WhatsAppService.is_duplicate_message(message_id):
                    logger.info(f"Duplicate webhook message {message_id} ignored.")
                    continue

                text_content = ""
                button_payload = None

                if msg_type == "text":
                    text_content = msg.get("text", {}).get("body", "")
                elif msg_type == "interactive":
                    interactive = msg.get("interactive", {})
                    if interactive.get("type") == "button_reply":
                        button_payload = interactive.get("button_reply", {}).get("id")
                        text_content = interactive.get("button_reply", {}).get("title", "")
                    elif interactive.get("type") == "list_reply":
                        button_payload = interactive.get("list_reply", {}).get("id")
                        text_content = interactive.get("list_reply", {}).get("title", "")

                if from_phone and (text_content or button_payload):
                    logger.info(f"Inbound WhatsApp from {from_phone}: '{text_content}'")
                    # Process via Conversation State Machine
                    replies, lang, state = await ConversationEngine.process_incoming_message(
                        db=db,
                        phone_number=from_phone,
                        message_text=text_content,
                        button_payload=button_payload
                    )

                    # Send outbound replies back to user
                    for reply_text in replies:
                        await WhatsAppService.send_text_message(
                            to_phone=from_phone,
                            message_text=reply_text
                        )

            # Check for delivery status updates from Meta
            statuses = value.get("statuses", [])
            for st in statuses:
                status_val = st.get("status")
                recipient_id = st.get("recipient_id")
                logger.info(f"WhatsApp message status update for {recipient_id}: {status_val}")

    return {"status": "ok"}
