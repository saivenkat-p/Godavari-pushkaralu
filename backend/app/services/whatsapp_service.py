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

        # Check configured provider
        has_twilio = bool(
            settings.TWILIO_ACCOUNT_SID and 
            settings.TWILIO_AUTH_TOKEN and 
            not settings.SIMULATION_MODE
        )
        has_meta = bool(
            settings.WHATSAPP_PHONE_NUMBER_ID and 
            settings.WHATSAPP_ACCESS_TOKEN and 
            not settings.SIMULATION_MODE
        )

        mode_str = "SIMULATED"
        if has_twilio:
            mode_str = "REAL_TWILIO_API"
        elif has_meta:
            mode_str = "REAL_META_API"

        log_entry = {
            "to": clean_phone,
            "text": message_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": mode_str
        }
        simulation_inbox.append(log_entry)
        if len(simulation_inbox) > 500:
            simulation_inbox.pop(0)

        # 1. Real Twilio WhatsApp Dispatch
        if has_twilio:
            twilio_url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
            formatted_to = f"whatsapp:+{clean_phone}" if not clean_phone.startswith("+") else f"whatsapp:{clean_phone}"
            auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            data = {
                "To": formatted_to,
                "From": settings.TWILIO_WHATSAPP_NUMBER,
                "Body": message_text
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(twilio_url, data=data, auth=auth)
                    if response.status_code in [200, 201]:
                        res_json = response.json()
                        logger.info(f"Twilio WhatsApp Success for {formatted_to}: {res_json.get('sid')}")
                        return {
                            "status": "DELIVERED_TO_PROVIDER",
                            "provider": "TWILIO",
                            "sid": res_json.get("sid")
                        }
                    else:
                        logger.error(f"Twilio WhatsApp Error ({response.status_code}): {response.text}")
                        return {
                            "status": "FAILED",
                            "error": response.text
                        }
            except Exception as e:
                logger.error(f"Failed to send Twilio WhatsApp message to {clean_phone}: {str(e)}")
                return {
                    "status": "FAILED",
                    "error": str(e)
                }

        # 2. Real Meta WhatsApp Business Platform Cloud API Call
        if has_meta:
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
                        "provider": "META",
                        "meta_response": data
                    }
            except Exception as e:
                logger.error(f"Failed to send real WhatsApp message to {clean_phone}: {str(e)}")
                return {
                    "status": "FAILED",
                    "error": str(e)
                }

        # 3. Fallback to simulation
        logger.info(f"[SIMULATED OUTBOUND WHATSAPP -> {clean_phone}]:\n{message_text}")
        return {
            "status": "SIMULATED_SUCCESS",
            "to": clean_phone,
            "message_id": f"sim_msg_{datetime.now(timezone.utc).timestamp()}"
        }

    @classmethod
    async def send_template_initiation(
        cls,
        to_phone: str,
        content_sid: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends a WhatsApp pre-approved template message to open the 24-hour conversational window.
        """
        clean_phone = to_phone.replace("+", "").replace("-", "").replace(" ", "")
        formatted_to = f"whatsapp:+{clean_phone}" if not clean_phone.startswith("+") else f"whatsapp:{clean_phone}"
        sid = content_sid or settings.TWILIO_CONTENT_SID
        if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and sid):
            return {"status": "SKIPPED", "reason": "No Twilio template credentials"}

        twilio_url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
        auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        data = {
            "To": formatted_to,
            "From": settings.TWILIO_WHATSAPP_NUMBER,
            "ContentSid": sid
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(twilio_url, data=data, auth=auth)
                logger.info(f"Twilio Template Initiation ({res.status_code}): {res.text}")
                return {"status": "DELIVERED" if res.status_code in [200, 201] else "FAILED", "response": res.text}
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}

