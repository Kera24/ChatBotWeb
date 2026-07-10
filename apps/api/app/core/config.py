from dataclasses import dataclass
from os import getenv


def _get_int(name: str, default: int) -> int:
    raw_value = getenv(name)
    if raw_value is None:
        return default
    return int(raw_value)


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
    REDIS_URL: str = getenv("REDIS_URL", "redis://localhost:6379/0")
    LOCAL_UPLOAD_ROOT: str = getenv("LOCAL_UPLOAD_ROOT", "./local_uploads")
    MAX_UPLOAD_BYTES: int = _get_int("MAX_UPLOAD_BYTES", 10 * 1024 * 1024)
    CHUNK_SIZE_WORDS: int = _get_int("CHUNK_SIZE_WORDS", 300)
    CHUNK_OVERLAP_WORDS: int = _get_int("CHUNK_OVERLAP_WORDS", 50)
    EMBEDDING_PROVIDER: str = getenv("EMBEDDING_PROVIDER", "local-mock")
    EMBEDDING_MODEL: str = getenv("EMBEDDING_MODEL", "local-mock-v1")
    EMBEDDING_DIMENSION: int = _get_int("EMBEDDING_DIMENSION", 1536)
    RETRIEVAL_MAX_CONTEXT_CHUNKS: int = _get_int("RETRIEVAL_MAX_CONTEXT_CHUNKS", 10)
    RETRIEVAL_MAX_CONTEXT_CHARS: int = _get_int("RETRIEVAL_MAX_CONTEXT_CHARS", 12000)
    PROMPT_VERSION: str = getenv("PROMPT_VERSION", "grounded-answer-v1")


settings = Settings()
