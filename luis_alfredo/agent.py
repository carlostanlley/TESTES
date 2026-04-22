"""
Núcleo do agente Luis Alfredo — máquina de estados e roteamento de mensagens.

process() recebe uma mensagem e devolve a lista de respostas a enviar,
cada uma com seu delay em segundos (0 = imediato).
O caller (server.py / n8n) é responsável por aplicar os delays.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .messages import (
    ACCEPTED_MIME_TYPES,
    AFTER_CLOSE_GREETING,
    BEFORE_OPEN_GREETING,
    BUSINESS_DOC_DETAILS,
    BUSINESS_DOC_IMMEDIATE,
    BUSINESS_GREETING,
    MEDIA_MESSAGE_TYPES,
    OFFHOURS_DOC_RECEIVED,
)
from .schedule import TimePeriod, current_period
from .state import ConvState, Conversation, store


@dataclass(frozen=True)
class IncomingMessage:
    """Mensagem normalizada recebida do lead."""
    conversation_id: str
    message_type: str           # "text", "image", "document", …
    text: str = ""
    mime_type: str = ""         # MIME type quando for mídia
    is_human_agent: bool = False  # True se veio de um atendente humano
    timestamp: datetime | None = None


@dataclass(frozen=True)
class OutgoingMessage:
    """Mensagem a ser enviada com delay opcional."""
    text: str
    delay_seconds: float = 0.0


def _is_document(msg: IncomingMessage) -> bool:
    """Detecta se a mensagem é uma imagem ou PDF de conta de luz."""
    if msg.message_type in MEDIA_MESSAGE_TYPES:
        return True
    if msg.mime_type.lower() in ACCEPTED_MIME_TYPES:
        return True
    return False


def _business_doc_flow() -> list[OutgoingMessage]:
    """Fluxo horário comercial após receber documento."""
    return [
        OutgoingMessage(text=BUSINESS_DOC_IMMEDIATE, delay_seconds=0),
        OutgoingMessage(text=BUSINESS_DOC_DETAILS, delay_seconds=5),
    ]


def _offhours_doc_flow() -> list[OutgoingMessage]:
    """Fluxo fora do horário após receber documento."""
    return [OutgoingMessage(text=OFFHOURS_DOC_RECEIVED, delay_seconds=0)]


def process(msg: IncomingMessage) -> list[OutgoingMessage]:
    """
    Processa uma mensagem e retorna as respostas do agente.
    Lista vazia = silêncio (não enviar nada).
    Efeito colateral: atualiza o estado da conversa no store.
    """
    cid = msg.conversation_id

    # ── Handover: humano assumiu ──────────────────────────────────────────────
    if msg.is_human_agent:
        store.handover(cid)
        return []

    conv: Conversation = store.get(cid)

    # ── Estado SILENT ou HANDOVER: silêncio total ─────────────────────────────
    if not conv.is_active:
        return []

    period = current_period(msg.timestamp)

    # ── Documento recebido (qualquer estado ativo) ────────────────────────────
    if _is_document(msg):
        if period == TimePeriod.BUSINESS:
            store.update(cid, ConvState.SILENT)
            return _business_doc_flow()
        else:
            store.update(cid, ConvState.SILENT)
            return _offhours_doc_flow()

    # ── Mensagem de texto ─────────────────────────────────────────────────────
    if conv.state == ConvState.GREETED:
        # Já saudado: aguarda documento em silêncio
        return []

    # Estado NEW: enviar saudação adequada ao período
    if period == TimePeriod.BUSINESS:
        store.update(cid, ConvState.GREETED)
        return [OutgoingMessage(text=BUSINESS_GREETING)]

    if period == TimePeriod.BEFORE_OPEN:
        store.update(cid, ConvState.GREETED)
        return [OutgoingMessage(text=BEFORE_OPEN_GREETING)]

    # AFTER_CLOSE (inclui fins de semana)
    store.update(cid, ConvState.GREETED)
    return [OutgoingMessage(text=AFTER_CLOSE_GREETING)]
