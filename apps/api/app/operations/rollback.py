from __future__ import annotations

import json
from pathlib import Path


def build_rollback_plan(current_manifest: str | Path, target_manifest: str | Path) -> dict:
    current = json.loads(Path(current_manifest).read_text(encoding="utf-8"))
    target = json.loads(Path(target_manifest).read_text(encoding="utf-8"))
    if current.get("protocol_major") != target.get("protocol_major"):
        raise ValueError("Cannot plan rollback across incompatible widget protocol majors.")
    if current.get("api_version") != target.get("api_version"):
        raise ValueError("Cannot plan rollback across incompatible public API versions.")
    return {
        "schema_version": "1.0",
        "mode": "dry_run",
        "from_sdk_version": current.get("sdk_version"),
        "to_sdk_version": target.get("sdk_version"),
        "major_alias_path": target.get("major_alias_path"),
        "immutable_loader_path": target.get("immutable_loader_path"),
        "target_commit": target.get("build_commit"),
        "required_verification": [
            "npm run widget:release:build",
            "npm run widget:pilot:verify",
            "npm run widget:pilot:readiness",
            "post-deploy real smoke in target environment",
        ],
    }

