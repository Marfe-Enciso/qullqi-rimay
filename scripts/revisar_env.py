"""Revisa backend/.env sin mostrar ningún valor secreto: solo dice si cada variable está lista."""
from pathlib import Path

env_path = Path(__file__).resolve().parent / "backend" / ".env"
keys = [
    "USE_EXTERNAL_SUPABASE", "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_JWT_SECRET", "CONSENT_SIGNING_SECRET", "USE_EXTERNAL_TWILIO", "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN", "TWILIO_WEBHOOK_URL", "USE_EXTERNAL_GEMINI", "GEMINI_API_KEY",
]
flags = {"USE_EXTERNAL_SUPABASE", "USE_EXTERNAL_TWILIO", "USE_EXTERNAL_GEMINI"}
values = {}
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip('"').strip("'")
else:
    print("NO EXISTE backend/.env")
for k in keys:
    v = values.get(k, "")
    if k in flags:
        state = v or "(vacío)"
    elif not v:
        state = "FALTA"
    elif v.upper().startswith(("REEMPLAZAR", "TU_")) or "REEMPLAZAR" in v.upper():
        state = "PENDIENTE (aún dice REEMPLAZAR)"
    else:
        state = f"OK ({len(v)} caracteres)"
    if k == "TWILIO_ACCOUNT_SID" and v:
        state += " | formato " + ("correcto (empieza con AC, 34)" if v.startswith("AC") and len(v) == 34 else "RARO: debe empezar con AC y tener 34 caracteres")
    if k == "TWILIO_AUTH_TOKEN" and v:
        state += " | formato " + ("correcto (32)" if len(v) == 32 else "RARO: debería tener 32 caracteres")
    if k == "TWILIO_WEBHOOK_URL" and v:
        state += " | " + ("termina bien en /api/twilio/webhook" if v.startswith("https://") and v.endswith("/api/twilio/webhook") else "REVISAR: debe ser https://.../api/twilio/webhook")
        state += " | trycloudflare" if "trycloudflare" in v else ""
    print(f"{k}: {state}")
