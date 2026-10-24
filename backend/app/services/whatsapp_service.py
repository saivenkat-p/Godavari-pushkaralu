import httpx
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from backend.app.core.config import settings

logger = logging.getLogger("whatsapp_service")

# In-memory deduplication set for webhooks (prevents processing retried Meta webhooks)
_processed_message_ids = set()
# Simulation message log for frontend simulator
simulation_inbox: List[Dict[str, Any]] = []


class WhatsAppService:
    GRAPH_API_URL = "https://graph.facebook.com"

    @classmethod
    def is_duplicate_message(cls, message_id: str) -> bool:
        if not message_id:
            return False
        if message_id in _processed_message_ids:
            return True
        _processed_message_ids.add(message_id)
        # Keep set bounded
        if len(_processed_message_ids) > 10000:
            _processed_message_ids.clear()
        return False

    @classmethod
    async def send_text_message(
        cls,
        to_phone: str,
        message_text: str,
        preview_url: bool = False
    ) -> Dict[str, Any]:
        """
        Sends an outbound WhatsApp text message.
        Uses real Meta Cloud API if credentials are provided, otherwise logs to simulation.
        """
        # Clean phone number (strip '+' or formatting)
        clean_phone = to_phone.replace("+", "").replace("-", "").replace(" ", "")

        # Check if real Meta credentials are configured
        has_real_credentials = bool(
            settings.WHATSAPP_PHONE_NUMBER_ID and 
            settings.WHATSAPP_ACCESS_TOKEN and 
            not settings.SIMULATION_MODE
        )

        log_entry = {
            "to": clean_phone,
            "text": message_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "REAL_META_API" if has_real_credentials else "SIMULATED"
        }
        simulation_inbox.append(log_entry)
        if len(simulation_inbox) > 500:
            simulation_inbox.pop(0)

        if not has_real_credentials:
            logger.info(f"[SIMULATED OUTBOUND WHATSAPP -> {clean_phone}]:\n{message_text}")
            return {
                "status": "SIMULATED_SUCCESS",
                "to": clean_phone,
                "message_id": f"sim_msg_{datetime.now(timezone.utc).timestamp()}"
            }

        # Real Meta WhatsApp Business Platform Cloud API Call
        url = f"{cls.GRAPH_API_URL}/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": message_text
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                logger.info(f"Meta WhatsApp Cloud API Success for {clean_phone}: {data}")
                return {
                    "status": "DELIVERED_TO_PROVIDER",
                    "meta_response": data
                }
        except Exception as e:
            logger.error(f"Failed to send real WhatsApp message to {clean_phone}: {str(e)}")
            return {
                "status": "FAILED",
                "error": str(e)
            }
