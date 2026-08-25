from __future__ import annotations

import base64
import hashlib
import io
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "SOURCE"
EXPECTED_SHA256 = "d1e11589703c92be2e50fd14b30791c73d537f2ed2751588963feac5ff6d340e"

parts = sorted(ROOT.glob("patch_payload.b64.*"))
if not parts:
    raise SystemExit("CSD v0.2.1 patch payload chunks were not found")

encoded = "".join(part.read_text(encoding="ascii").strip() for part in parts)
payload = base64.b64decode(encoded, validate=True)
actual = hashlib.sha256(payload).hexdigest()
if actual != EXPECTED_SHA256:
    raise SystemExit(f"CSD v0.2.1 patch payload SHA-256 mismatch: {actual}")

with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
    members = archive.getmembers()
    for member in members:
        path = Path(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"Unsafe patch member: {member.name}")
    archive.extractall(SOURCE)

print(f"Applied CSD v0.2.1 patch payload: {len(members)} files, sha256={actual}")
