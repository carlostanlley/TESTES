"""
Gerenciamento de estado das conversas.
Usa dicionário em memória com TTL. Para escala, substitua por Redis.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

_TZ = ZoneInfo("America/Fortaleza")
_TTL = timedelta(hours=24)


class ConvState(str, Enum):
    NEW = "new"           # sem interação ainda
    GREETED = "greeted"   # saudação enviada, aguardando documento
    SILENT = "silent"     # fluxo concluído — silêncio total
    HANDOVER = "handover" # humano assumiu


@dataclass
class Conversation:
    state: ConvState = ConvState.NEW
    turns: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(_TZ))
    last_activity: datetime = field(default_factory=lambda: datetime.now(_TZ))

    def touch(self) -> None:
        self.last_activity = datetime.now(_TZ)
        self.turns += 1

    @property
    def is_active(self) -> bool:
        return self.state not in (ConvState.SILENT, ConvState.HANDOVER)

    @property
    def is_expired(self) -> bool:
        return (datetime.now(_TZ) - self.last_activity) > _TTL


class StateStore:
    """Thread-safe store de estados de conversa."""

    def __init__(self) -> None:
        self._store: dict[str, Conversation] = {}
        self._lock = threading.Lock()

    def get(self, conversation_id: str) -> Conversation:
        with self._lock:
            conv = self._store.get(conversation_id)
            if conv is None or conv.is_expired:
                conv = Conversation()
                self._store[conversation_id] = conv
            return conv

    def update(self, conversation_id: str, state: ConvState) -> None:
        with self._lock:
            conv = self._store.setdefault(conversation_id, Conversation())
            conv.state = state
            conv.touch()

    def handover(self, conversation_id: str) -> None:
        with self._lock:
            conv = self._store.setdefault(conversation_id, Conversation())
            conv.state = ConvState.HANDOVER
            conv.touch()

    def reset(self, conversation_id: str) -> None:
        with self._lock:
            self._store[conversation_id] = Conversation()

    def purge_expired(self) -> int:
        """Remove conversas expiradas. Retorna a quantidade removida."""
        with self._lock:
            expired = [k for k, v in self._store.items() if v.is_expired]
            for k in expired:
                del self._store[k]
            return len(expired)

    def snapshot(self) -> dict[str, dict]:
        with self._lock:
            return {
                cid: {
                    "state": c.state,
                    "turns": c.turns,
                    "created_at": c.created_at.isoformat(),
                    "last_activity": c.last_activity.isoformat(),
                }
                for cid, c in self._store.items()
            }


# Instância global — compartilhada entre os handlers
store = StateStore()
