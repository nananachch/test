from __future__ import annotations

import base64
import hashlib
import io
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "SOURCE"


def apply_payload(prefix: str, expected_sha256: str, label: str) -> None:
    parts = sorted(ROOT.glob(f"{prefix}.b64.*"))
    if not parts:
        raise SystemExit(f"{label} chunks were not found")

    encoded = "".join(part.read_text(encoding="ascii").strip() for part in parts)
    payload = base64.b64decode(encoded, validate=True)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected_sha256:
        raise SystemExit(f"{label} SHA-256 mismatch: {actual}")

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise SystemExit(f"Unsafe payload member: {member.name}")
        archive.extractall(SOURCE)

    print(f"Applied {label}: {len(members)} files, sha256={actual}")


apply_payload(
    "supplement_payload",
    "b4eb55890e8205fd36bf62065fa258ebaa00540a4e2b68e5354a06b0925f39d1",
    "CSD v0.2.1 supplement payload",
)

apply_payload(
    "patch_payload",
    "d1e11589703c92be2e50fd14b30791c73d537f2ed2751588963feac5ff6d340e",
    "CSD v0.2.1 patch payload",
)

apply_payload(
    "hotfix2_payload",
    "e43a2e447ed28afe4197c6cb535bf2020231d7db01b5294871a36c0f07d42b6d",
    "CSD v0.2.1 compile hotfix payload",
)
