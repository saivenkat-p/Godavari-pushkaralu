import os
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    APP_SECRET_KEY: str = "bandham-qr-dev-secret-key-change-in-production-2027"
    PORT: int = 8001
    HOST: str = "0.0.0.0"
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    DATABASE_URL: str = "sqlite+aiosqlite:///./bandham_qr.db"

    # Meta WhatsApp Business Platform Cloud API
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "bandham_pushkaralu_verify_token_2027"
    WHATSAPP_APP_SECRET: str = ""
    WHATSAPP_API_VERSION: str = "v19.0"

    PUBLIC_BASE_URL: str = "http://localhost:5173"
    SIMULATION_MODE: bool = True

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }


settings = Settings()
