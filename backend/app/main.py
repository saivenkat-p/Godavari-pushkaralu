import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.core.database import engine, Base, AsyncSessionLocal
from backend.app.core.seed_data import seed_database
from backend.app.api import (
    whatsapp_webhook, simulator, auth, registration, cases, scan, sanitation, verified_services, audit
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("bandham_main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite / PostgreSQL tables
    logger.info("Initializing Bandham QR Database Schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Run synthetic seed data generator
    async with AsyncSessionLocal() as session:
        await seed_database(session)
    logger.info("Database initialized and verified.")
    yield


app = FastAPI(
    title="Godavari Pushkaralu 2027 — Bandham QR Family Safety & Pilgrim Grid",
    description="WhatsApp-first public service assistant and operations grid backend.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows local dev and public QR mobile scan
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(whatsapp_webhook.router)
app.include_router(simulator.router)
app.include_router(auth.router)
app.include_router(registration.router)
app.include_router(cases.router)
app.include_router(scan.router)
app.include_router(sanitation.router)
app.include_router(verified_services.router)
app.include_router(audit.router)


@app.get("/api/health")
async def health_check():
    return {
        "status": "HEALTHY",
        "service": "Bandham QR Godavari Pushkaralu 2027",
        "environment": settings.ENVIRONMENT,
        "simulation_mode": settings.SIMULATION_MODE,
        "whatsapp_api_configured": bool(settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_ACCESS_TOKEN)
    }
