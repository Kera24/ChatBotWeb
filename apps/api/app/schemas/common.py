from typing import Any


def success_response(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "meta": meta or {},
    }
