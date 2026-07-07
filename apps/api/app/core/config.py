from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    PROJECT_NAME: str = getenv("PROJECT_NAME", "ChatBotWeb / Yoranix AI Platform")
    PROJECT_DESCRIPTION: str = getenv(
        "PROJECT_DESCRIPTION",
        "Multi-tenant AI knowledge platform API",
    )
    VERSION: str = getenv("VERSION", "0.1.0")
    PHASE: str = getenv("PHASE", "mvp-foundation")
    SERVICE_NAME: str = getenv("SERVICE_NAME", "chatbotweb-api")
    API_V1_PREFIX: str = getenv("API_V1_PREFIX", "/api/v1")
    DATABASE_URL: str = getenv("DATABASE_URL", "sqlite:///./local.db")


settings = Settings()
