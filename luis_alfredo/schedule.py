"""
Lógica de horário comercial em America/Fortaleza (UTC-3, sem horário de verão).
Segunda a Sexta, das 08h00 às 18h00.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

TZ = ZoneInfo("America/Fortaleza")

_OPEN_HOUR = 8   # 08:00 inclusive
_CLOSE_HOUR = 18  # 18:00 exclusive (a partir das 18:00:00 está fechado)


class TimePeriod(str, Enum):
    BUSINESS = "business"       # dentro do horário comercial
    BEFORE_OPEN = "before_open" # antes das 08h (hoje ainda não abriu)
    AFTER_CLOSE = "after_close" # após as 18h ou fim de semana


def current_period(now: datetime | None = None) -> TimePeriod:
    """Retorna o período atual baseado no horário de Fortaleza."""
    if now is None:
        now = datetime.now(TZ)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=TZ)

    # Fins de semana → fechado (usa AFTER_CLOSE para mensagem padrão de retorno)
    if now.weekday() >= 5:  # 5 = sábado, 6 = domingo
        return TimePeriod.AFTER_CLOSE

    open_dt = now.replace(hour=_OPEN_HOUR, minute=0, second=0, microsecond=0)
    close_dt = now.replace(hour=_CLOSE_HOUR, minute=0, second=0, microsecond=0)

    if now < open_dt:
        return TimePeriod.BEFORE_OPEN
    if now >= close_dt:
        return TimePeriod.AFTER_CLOSE
    return TimePeriod.BUSINESS


def is_business_hours(now: datetime | None = None) -> bool:
    return current_period(now) == TimePeriod.BUSINESS
