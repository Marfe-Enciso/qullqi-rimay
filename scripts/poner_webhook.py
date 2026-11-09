"""Espera la dirección del túnel de cloudflared y la pone en backend/.env como TWILIO_WEBHOOK_URL.
No muestra ni toca ninguna otra clave."""
import re, sys, time
from pathlib import Path

root = Path(__file__).resolve().parent
log = root / "tunnel_log.txt"
env = root / "backend" / ".env"
pat = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

url = None
for _ in range(90):
    if log.exists():
        m = pat.search(log.read_text(encoding="utf-8", errors="replace"))
        if m:
            url = m.group(0)
            break
    time.sleep(1)
if not url:
    print("No se pudo obtener la dirección del túnel. Revisa tunnel_log.txt")
    sys.exit(1)

webhook = url + "/api/twilio/webhook"
raw = env.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
text = raw.decode("utf-8-sig", errors="replace")
nl = "\r\n" if "\r\n" in text else "\n"
lines = text.splitlines()
done = False
for i, line in enumerate(lines):
    if line.strip().startswith("TWILIO_WEBHOOK_URL"):
        lines[i] = f"TWILIO_WEBHOOK_URL={webhook}"
        done = True
if not done:
    lines.append(f"TWILIO_WEBHOOK_URL={webhook}")
out = nl.join(lines) + nl
env.write_bytes((b"\xef\xbb\xbf" if bom else b"") + out.encode("utf-8"))
(root / "webhook_url.txt").write_text(webhook + "\n", encoding="utf-8")
print()
print("=" * 70)
print("PEGA ESTA DIRECCION EN TWILIO (Sandbox settings > When a message comes in, POST):")
print(webhook)
print("=" * 70)
print()
