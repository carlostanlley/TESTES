"""
Servidor webhook FastAPI — Luis Alfredo Agent.

Endpoints:
  POST /webhook/message   — recebe mensagem do lead (via n8n / WhatsApp API)
  POST /webhook/handoff   — notifica que humano assumiu a conversa
  DELETE /admin/reset/{id} — reseta estado de uma conversa (testes/admin)
  GET  /admin/state/{id}  — consulta estado atual de uma conversa
  GET  /admin/store       — snapshot de todas as conversas ativas
  GET  /health            — health check

Compatível com Evolution API, Z-API, Twilio ou n8n como intermediário.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .agent import IncomingMessage, OutgoingMessage, process
from .state import store

# ── Logging estruturado (audit trail) ────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":%(message)s}',
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("luis_alfredo")


def _log(event: str, **kwargs: Any) -> None:
    import json
    log.info(json.dumps({"event": event, "ts": datetime.utcnow().isoformat(), **kwargs}))


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Luis Alfredo Agent",
    description="Agente de atendimento — Empréstimo na Conta de Luz (Crefaz)",
    version="1.0.0",
    docs_url="/docs",
)

API_SECRET = os.environ.get("AGENT_API_SECRET", "")  # deixe vazio para desabilitar auth


def _check_secret(request: Request) -> None:
    if not API_SECRET:
        return
    token = request.headers.get("X-API-Secret", "")
    if token != API_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Schemas de entrada ────────────────────────────────────────────────────────

class MessagePayload(BaseModel):
    """
    Mensagem normalizada enviada pelo integrador (n8n ou WhatsApp API adapter).
    """
    conversation_id: str = Field(..., description="ID único da conversa (ex: número WhatsApp)")
    message_type: str = Field(
        default="text",
        description="Tipo: text | image | document | audio | video | ...",
    )
    text: str = Field(default="", description="Conteúdo textual (se houver)")
    mime_type: str = Field(default="", description="MIME type da mídia (se houver)")
    is_human_agent: bool = Field(
        default=False,
        description="True se a mensagem veio de um atendente humano (handover via mensagem)",
    )
    timestamp: datetime | None = Field(
        default=None,
        description="Timestamp da mensagem (None = usa horário atual do servidor)",
    )


class HandoffPayload(BaseModel):
    conversation_id: str


# ── Schemas de saída ──────────────────────────────────────────────────────────

class MessageOut(BaseModel):
    text: str
    delay_seconds: float


class WebhookResponse(BaseModel):
    conversation_id: str
    agent_active: bool          # False = silêncio; caller não deve enviar mensagens extras
    new_state: str
    messages: list[MessageOut]  # lista de mensagens a enviar com seus delays


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/webhook/message", response_model=WebhookResponse)
async def webhook_message(payload: MessagePayload, request: Request) -> WebhookResponse:
    """Recebe uma mensagem do lead e retorna as respostas do agente."""
    _check_secret(request)

    msg = IncomingMessage(
        conversation_id=payload.conversation_id,
        message_type=payload.message_type,
        text=payload.text,
        mime_type=payload.mime_type,
        is_human_agent=payload.is_human_agent,
        timestamp=payload.timestamp,
    )

    _log(
        "message_received",
        cid=payload.conversation_id,
        type=payload.message_type,
        mime=payload.mime_type,
        is_human=payload.is_human_agent,
    )

    responses: list[OutgoingMessage] = process(msg)
    conv = store.get(payload.conversation_id)

    _log(
        "agent_response",
        cid=payload.conversation_id,
        state=conv.state,
        n_messages=len(responses),
    )

    return WebhookResponse(
        conversation_id=payload.conversation_id,
        agent_active=conv.is_active,
        new_state=conv.state,
        messages=[
            MessageOut(text=r.text, delay_seconds=r.delay_seconds)
            for r in responses
        ],
    )


@app.post("/webhook/handoff", status_code=200)
async def webhook_handoff(payload: HandoffPayload, request: Request) -> dict:
    """
    Notifica que um atendente humano assumiu a conversa.
    O agente entra em HANDOVER e para de responder.
    """
    _check_secret(request)
    store.handover(payload.conversation_id)
    _log("handover", cid=payload.conversation_id)
    return {"status": "ok", "conversation_id": payload.conversation_id, "state": "handover"}


@app.delete("/admin/reset/{conversation_id}", status_code=200)
async def admin_reset(conversation_id: str, request: Request) -> dict:
    """Reseta o estado de uma conversa (útil para testes)."""
    _check_secret(request)
    store.reset(conversation_id)
    _log("reset", cid=conversation_id)
    return {"status": "ok", "conversation_id": conversation_id}


@app.get("/admin/state/{conversation_id}")
async def admin_state(conversation_id: str, request: Request) -> dict:
    """Consulta o estado atual de uma conversa."""
    _check_secret(request)
    conv = store.get(conversation_id)
    return {
        "conversation_id": conversation_id,
        "state": conv.state,
        "turns": conv.turns,
        "is_active": conv.is_active,
        "last_activity": conv.last_activity.isoformat(),
    }


@app.get("/admin/store")
async def admin_store(request: Request) -> dict:
    """Snapshot de todas as conversas ativas (para debug/monitoramento)."""
    _check_secret(request)
    return store.snapshot()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "agent": "luis_alfredo", "version": "1.0.0"}


# ── Limpeza periódica ─────────────────────────────────────────────────────────

@app.on_event("startup")
async def start_purge_task() -> None:
    """Inicia tarefa de limpeza de conversas expiradas a cada hora."""
    async def _purge_loop() -> None:
        while True:
            await asyncio.sleep(3600)
            removed = store.purge_expired()
            if removed:
                _log("purge_expired", removed=removed)

    asyncio.create_task(_purge_loop())
