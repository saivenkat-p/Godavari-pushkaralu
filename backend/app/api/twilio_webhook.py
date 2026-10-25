import logging
from fastapi import APIRouter, Request, Response, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from backend.app.core.database import get_db
from backend.app.services.whatsapp_service import WhatsAppService
from backend.app.services.conversation_engine import ConversationEngine

logger = logging.getLogger("twilio_webhook")
router = APIRouter(prefix="/api/webhook/twilio", tags=["Twilio WhatsApp Webhook"])


@router.post("/whatsapp")
async def receive_twilio_whatsapp(
    request: Request,
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None),
    Body: Optional[str] = Form(None),
    MessageSid: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Inbound webhook for Twilio WhatsApp messages.
    When a user replies on real WhatsApp, Twilio posts here.
    """
    # If form data wasn't auto-parsed, read form manually
    if not From or not Body:
        form_data = await request.form()
        From = form_data.get("From") or From or ""
        Body = form_data.get("Body") or Body or ""
        MessageSid = form_data.get("MessageSid") or MessageSid or ""

    clean_from = str(From).replace("whatsapp:", "").strip()
    msg_text = str(Body).strip()

    logger.info(f"Incoming Twilio WhatsApp from {clean_from} (SID: {MessageSid}): '{msg_text}'")

    if not clean_from or not msg_text:
        return Response(content="<Response></Response>", media_type="application/xml")

    # Deduplicate
    if WhatsAppService.is_duplicate_message(str(MessageSid)):
        logger.info(f"Duplicate Twilio message {MessageSid} ignored.")
        return Response(content="<Response></Response>", media_type="application/xml")

    # Process through Bandham conversation engine state machine
    try:
        replies, lang, state = await ConversationEngine.process_incoming_message(
            db=db,
            phone_number=clean_from,
            message_text=msg_text
        )

        # Build TwiML XML response so Twilio delivers replies directly back to WhatsApp
        if replies:
            import html
            xml_messages = "".join([f"<Message><Body>{html.escape(r)}</Body></Message>" for r in replies])
            twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response>{xml_messages}</Response>'
            logger.info(f"Returning TwiML response with {len(replies)} message(s) to Twilio.")
            return Response(content=twiml, media_type="application/xml")

    except Exception as e:
        logger.error(f"Error handling Twilio WhatsApp message: {str(e)}", exc_info=True)

    # Empty TwiML response fallback
    return Response(content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="application/xml")
