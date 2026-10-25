import asyncio
import logging
import httpx
import os
import sys

# Configure stdout and stderr for UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from backend.app.core.database import AsyncSessionLocal
from backend.app.services.conversation_engine import ConversationEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("telegram_bot")


async def run_telegram_bot(token: str):
    base_url = f"https://api.telegram.org/bot{token}"
    offset = 0

    async with httpx.AsyncClient(timeout=35.0) as client:
        # Verify bot token
        try:
            me_res = await client.get(f"{base_url}/getMe")
            if me_res.status_code != 200:
                print(f"[ERROR] Invalid Telegram Bot Token: {me_res.text}")
                return
            bot_info = me_res.json().get("result", {})
            username = bot_info.get("username")
            first_name = bot_info.get("first_name")
            print(f"\n=======================================================")
            print(f"[ONLINE] TELEGRAM BOT ACTIVE: @{username} ({first_name})")
            print(f"[LINK] Open in Telegram: https://t.me/{username}")
            print(f"=======================================================\n", flush=True)
        except Exception as e:
            print(f"[ERROR] connecting to Telegram API: {e}", flush=True)
            return

        # Start long polling
        print("[POLLING] Waiting for messages from pilgrims...", flush=True)
        while True:
            try:
                res = await client.get(
                    f"{base_url}/getUpdates",
                    params={"offset": offset, "timeout": 25}
                )
                if res.status_code == 200:
                    data = res.json()
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        msg = update.get("message")
                        if not msg:
                            continue

                        chat_id = str(msg.get("chat", {}).get("id"))
                        user_first_name = msg.get("from", {}).get("first_name", "Pilgrim")
                        text = msg.get("text", "").strip()

                        if not text:
                            continue

                        print(f"[INCOMING] from {user_first_name} ({chat_id}): '{text}'", flush=True)

                        # Handle /start command as initial Telugu greeting
                        if text == "/start":
                            text = "నమస్కారం"

                        # Process via ConversationEngine state machine
                        async with AsyncSessionLocal() as db:
                            replies, lang, state = await ConversationEngine.process_incoming_message(
                                db=db,
                                phone_number=f"TG_{chat_id}",
                                message_text=text
                            )

                            for reply in replies:
                                print(f"[OUTBOUND] to {chat_id}: {reply[:60]}...", flush=True)
                                try:
                                    # Send as plain text or markdown fallback
                                    send_res = await client.post(
                                        f"{base_url}/sendMessage",
                                        json={
                                            "chat_id": chat_id,
                                            "text": reply,
                                        }
                                    )
                                    if send_res.status_code != 200:
                                        logger.warning(f"Telegram send failed ({send_res.status_code}): {send_res.text}")
                                except Exception as err:
                                    logger.error(f"Failed to send message: {err}")

            except asyncio.CancelledError:
                print("Telegram bot polling stopped.", flush=True)
                break
            except Exception as e:
                logger.error(f"Telegram polling loop error: {e}")
                await asyncio.sleep(2)


if __name__ == "__main__":
    token = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Usage: python telegram_bot.py <TELEGRAM_BOT_TOKEN>")
        sys.exit(1)
    asyncio.run(run_telegram_bot(token))
