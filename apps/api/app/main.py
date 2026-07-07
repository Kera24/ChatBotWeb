from fastapi import FastAPI

app = FastAPI(
    title="ChatBotWeb API",
    description="Multi-tenant AI knowledge platform API",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "chatbotweb-api"}


@app.get("/api/v1/system/info")
def system_info() -> dict[str, str]:
    return {
        "name": "ChatBotWeb / Yoranix AI Platform",
        "phase": "mvp-foundation",
    }
