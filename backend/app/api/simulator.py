from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from backend.app.core.database import get_db
from backend.app.schemas.schemas import SimulatorMessageRequest, SimulatorMessageResponse
from backend.app.services.conversation_engine import ConversationEngine
from backend.app.services.whatsapp_service import simulation_inbox

router = APIRouter(prefix="/api/simulator", tags=["WhatsApp Simulator"])


@router.post("/chat", response_model=SimulatorMessageResponse)
async def chat_simulator(
    req: SimulatorMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Simulates sending an incoming message to the WhatsApp assistant.
    Returns the automated bot replies and updated state.
    """
    replies, lang, state = await ConversationEngine.process_incoming_message(
        db=db,
        phone_number=req.phone_number,
        message_text=req.message_text,
        button_payload=req.button_payload
    )

    # Record outbound messages into simulation inbox
    for rep in replies:
        simulation_inbox.append({
            "to": req.phone_number,
            "text": rep,
            "mode": "SIMULATED"
        })

    return {
        "replies": replies,
        "session_language": lang,
        "current_state": state
    }


@router.get("/inbox", response_model=List[Dict[str, Any]])
async def get_simulation_inbox():
    """
    Retrieves recent outbound WhatsApp messages for testing and evaluation.
    """
    return list(reversed(simulation_inbox[-50:]))


@router.post("/reset")
async def reset_simulation(
    phone_number: str = "919876543210",
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import delete
    from backend.app.models.models import ConversationSession
    await db.execute(delete(ConversationSession).where(ConversationSession.phone_number == phone_number))
    await db.commit()
    return {"status": "reset_successful", "phone": phone_number}
