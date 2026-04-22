"""
Testes unitários do agente Luis Alfredo.
Cobrem todos os fluxos definidos no prompt.

Execute com:
    python -m pytest luis_alfredo/tests.py -v
ou:
    python luis_alfredo/tests.py
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from unittest.mock import patch

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

from . import process, store
from .agent import IncomingMessage
from .messages import (
    AFTER_CLOSE_GREETING,
    BEFORE_OPEN_GREETING,
    BUSINESS_DOC_BENEFITS,
    BUSINESS_DOC_CLOSING,
    BUSINESS_DOC_IMMEDIATE,
    BUSINESS_DOC_INTRO,
    BUSINESS_GREETING,
    OFFHOURS_DOC_RECEIVED,
)
from .schedule import TimePeriod, current_period
from .state import ConvState

TZ = ZoneInfo("America/Fortaleza")


def _make_dt(weekday: int, hour: int, minute: int = 0) -> datetime:
    """Cria datetime no fuso Fortaleza para um dia da semana específico."""
    # 2024-01-01 = segunda-feira (weekday 0)
    base = datetime(2024, 1, 1, tzinfo=TZ)
    delta_days = weekday - base.weekday()
    from datetime import timedelta
    d = base + timedelta(days=delta_days)
    return d.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _text_msg(cid: str, ts: datetime | None = None) -> IncomingMessage:
    return IncomingMessage(conversation_id=cid, message_type="text", text="oi", timestamp=ts)


def _doc_msg(cid: str, ts: datetime | None = None, mime: str = "image/jpeg") -> IncomingMessage:
    return IncomingMessage(conversation_id=cid, message_type="image", mime_type=mime, timestamp=ts)


def _pdf_msg(cid: str, ts: datetime | None = None) -> IncomingMessage:
    return IncomingMessage(conversation_id=cid, message_type="document", mime_type="application/pdf", timestamp=ts)


def _human_msg(cid: str) -> IncomingMessage:
    return IncomingMessage(conversation_id=cid, message_type="text", is_human_agent=True)


# ── Horário comercial ─────────────────────────────────────────────────────────

BUSINESS_TS = _make_dt(0, 10)  # segunda, 10h → dentro do horário
BEFORE_TS = _make_dt(0, 7)     # segunda, 07h → antes das 08h
AFTER_TS = _make_dt(0, 19)     # segunda, 19h → após as 18h
WEEKEND_TS = _make_dt(5, 10)   # sábado, 10h → fim de semana


class TestSchedule(unittest.TestCase):

    def test_business_hours(self):
        self.assertEqual(current_period(BUSINESS_TS), TimePeriod.BUSINESS)

    def test_before_open(self):
        self.assertEqual(current_period(BEFORE_TS), TimePeriod.BEFORE_OPEN)

    def test_after_close(self):
        self.assertEqual(current_period(AFTER_TS), TimePeriod.AFTER_CLOSE)

    def test_weekend_is_after_close(self):
        self.assertEqual(current_period(WEEKEND_TS), TimePeriod.AFTER_CLOSE)

    def test_exactly_at_open(self):
        ts = _make_dt(0, 8, 0)
        self.assertEqual(current_period(ts), TimePeriod.BUSINESS)

    def test_exactly_at_close(self):
        ts = _make_dt(0, 18, 0)
        self.assertEqual(current_period(ts), TimePeriod.AFTER_CLOSE)

    def test_one_minute_before_close(self):
        ts = _make_dt(0, 17, 59)
        self.assertEqual(current_period(ts), TimePeriod.BUSINESS)


class TestBusinessHoursFlow(unittest.TestCase):

    def setUp(self):
        store.reset("test_bh")

    # Passo 1: primeiro contato → saudação comercial
    def test_step1_business_greeting(self):
        responses = process(_text_msg("test_bh", BUSINESS_TS))
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0].text, BUSINESS_GREETING)
        self.assertEqual(responses[0].delay_seconds, 0)
        self.assertEqual(store.get("test_bh").state, ConvState.GREETED)

    # Passo 2: documento → 4 mensagens com delays 0, 5, 5, 5
    def test_step2_document_four_messages(self):
        process(_text_msg("test_bh", BUSINESS_TS))  # greet first
        responses = process(_doc_msg("test_bh", BUSINESS_TS))
        self.assertEqual(len(responses), 4)
        self.assertEqual(responses[0].text, BUSINESS_DOC_IMMEDIATE)
        self.assertEqual(responses[0].delay_seconds, 0)
        self.assertEqual(responses[1].text, BUSINESS_DOC_INTRO)
        self.assertEqual(responses[1].delay_seconds, 5)
        self.assertEqual(responses[2].text, BUSINESS_DOC_BENEFITS)
        self.assertEqual(responses[2].delay_seconds, 5)
        self.assertEqual(responses[3].text, BUSINESS_DOC_CLOSING)
        self.assertEqual(responses[3].delay_seconds, 5)

    def test_step2_pdf_accepted(self):
        responses = process(_pdf_msg("test_bh", BUSINESS_TS))
        self.assertEqual(responses[0].text, BUSINESS_DOC_IMMEDIATE)

    # Após Passo 2: silêncio total
    def test_silence_after_document(self):
        process(_doc_msg("test_bh", BUSINESS_TS))
        responses = process(_text_msg("test_bh", BUSINESS_TS))
        self.assertEqual(responses, [])

    # Já saudado: texto adicional → silêncio
    def test_greeted_text_is_silent(self):
        process(_text_msg("test_bh", BUSINESS_TS))  # first → greeted
        responses = process(_text_msg("test_bh", BUSINESS_TS))  # second → silent
        self.assertEqual(responses, [])

    # Documento sem saudação prévia também funciona
    def test_document_without_prior_greeting(self):
        responses = process(_doc_msg("test_bh", BUSINESS_TS))
        self.assertEqual(len(responses), 4)
        self.assertEqual(store.get("test_bh").state, ConvState.SILENT)


class TestOffHoursFlow(unittest.TestCase):

    def setUp(self):
        store.reset("test_oh")

    def test_before_open_greeting(self):
        responses = process(_text_msg("test_oh", BEFORE_TS))
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0].text, BEFORE_OPEN_GREETING)

    def test_after_close_greeting(self):
        responses = process(_text_msg("test_oh", AFTER_TS))
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0].text, AFTER_CLOSE_GREETING)

    def test_weekend_greeting(self):
        responses = process(_text_msg("test_oh", WEEKEND_TS))
        self.assertEqual(responses[0].text, AFTER_CLOSE_GREETING)

    def test_offhours_document_received(self):
        responses = process(_doc_msg("test_oh", AFTER_TS))
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0].text, OFFHOURS_DOC_RECEIVED)
        self.assertEqual(store.get("test_oh").state, ConvState.SILENT)

    # Após confirmação fora do horário: silêncio total
    def test_silence_after_offhours_document(self):
        process(_doc_msg("test_oh", AFTER_TS))
        responses = process(_text_msg("test_oh", AFTER_TS))
        self.assertEqual(responses, [])

    def test_before_open_then_document(self):
        process(_text_msg("test_oh", BEFORE_TS))
        responses = process(_doc_msg("test_oh", BEFORE_TS))
        self.assertEqual(responses[0].text, OFFHOURS_DOC_RECEIVED)


class TestHandover(unittest.TestCase):

    def setUp(self):
        store.reset("test_ho")

    def test_human_message_triggers_handover(self):
        responses = process(_human_msg("test_ho"))
        self.assertEqual(responses, [])
        self.assertEqual(store.get("test_ho").state, ConvState.HANDOVER)

    def test_agent_silent_after_handover(self):
        process(_human_msg("test_ho"))
        responses = process(_text_msg("test_ho", BUSINESS_TS))
        self.assertEqual(responses, [])

    def test_handover_via_store(self):
        store.handover("test_ho")
        responses = process(_text_msg("test_ho", BUSINESS_TS))
        self.assertEqual(responses, [])


class TestStateReset(unittest.TestCase):

    def test_reset_restarts_conversation(self):
        cid = "test_reset"
        process(_doc_msg(cid, BUSINESS_TS))  # → SILENT
        store.reset(cid)
        responses = process(_text_msg(cid, BUSINESS_TS))
        self.assertEqual(responses[0].text, BUSINESS_GREETING)


class TestMimeTypes(unittest.TestCase):

    def setUp(self):
        store.reset("test_mime")

    def _assert_triggers_doc_flow(self, mime: str):
        store.reset("test_mime")
        msg = IncomingMessage(
            conversation_id="test_mime",
            message_type="document",
            mime_type=mime,
            timestamp=BUSINESS_TS,
        )
        responses = process(msg)
        self.assertTrue(len(responses) > 0, f"MIME {mime!r} não gerou resposta")

    def test_jpeg(self):
        self._assert_triggers_doc_flow("image/jpeg")

    def test_png(self):
        self._assert_triggers_doc_flow("image/png")

    def test_webp(self):
        self._assert_triggers_doc_flow("image/webp")

    def test_pdf(self):
        self._assert_triggers_doc_flow("application/pdf")

    def test_audio_ignored(self):
        store.reset("test_mime")
        msg = IncomingMessage(
            conversation_id="test_mime",
            message_type="audio",
            mime_type="audio/ogg",
            timestamp=BUSINESS_TS,
        )
        responses = process(msg)
        # Audio não é documento — deve tratar como texto (saudação)
        self.assertEqual(responses[0].text, BUSINESS_GREETING)


if __name__ == "__main__":
    unittest.main(verbosity=2)
