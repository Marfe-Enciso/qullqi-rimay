"""Gestor de Sandboxes Efímeros Aislados para la Demostración Pública Ficticia de Rosa (Huamanga).

Garantías de seguridad y demostración (Prioridades 1.5 y 4):
- Cada visitante del modo demostración sin registro opera sobre una instancia
  `InMemoryStore(use_supabase=False, use_enriched_demo=True)` completamente aislada en memoria RAM,
  precargada con los 133 movimientos ficticios coherentes de Rosa (Semanas 1 a 7) y Semana 8 en vivo.
- Ninguna operación del sandbox de demostración puede leer, escribir, confirmar, revocar ni alterar
  la base de datos compartida en Supabase PostgreSQL (`oqbfuyxoclufkikaddoj`), ni acceder a datos
  de otras sesiones o a operaciones administrativas.
"""

from collections import OrderedDict
import re
from threading import Lock
from app.services.store import InMemoryStore

MAX_ACTIVE_SANDBOXES = 100
_SAFE_VISITOR_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{4,64}$")


class DemoSandboxManager:
    def __init__(self) -> None:
        self._lock = Lock()
        self._sandboxes: OrderedDict[str, InMemoryStore] = OrderedDict()

    def _normalize_visitor_id(self, visitor_id: str) -> str:
        cleaned = (visitor_id or "").strip()
        if not _SAFE_VISITOR_ID_RE.match(cleaned):
            return "default-public-demo-sandbox"
        return cleaned

    def get_sandbox(self, visitor_id: str) -> InMemoryStore:
        key = self._normalize_visitor_id(visitor_id)
        with self._lock:
            if key in self._sandboxes:
                self._sandboxes.move_to_end(key)
                return self._sandboxes[key]
            while len(self._sandboxes) >= MAX_ACTIVE_SANDBOXES:
                self._sandboxes.popitem(last=False)
            sandbox = InMemoryStore(use_supabase=False, use_enriched_demo=True)
            self._sandboxes[key] = sandbox
            return sandbox

    def reset_sandbox(self, visitor_id: str) -> InMemoryStore:
        key = self._normalize_visitor_id(visitor_id)
        with self._lock:
            sandbox = InMemoryStore(use_supabase=False, use_enriched_demo=True)
            self._sandboxes[key] = sandbox
            self._sandboxes.move_to_end(key)
            return sandbox


demo_sandbox_manager = DemoSandboxManager()
