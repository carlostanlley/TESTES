"""
Agente de IA altamente humano e inteligente — construído com Anthropic SDK.

Características:
  - Personalidade rica e autêntica
  - Raciocínio adaptativo (thinking: adaptive)
  - Memória de conversa com compactação automática
  - Prompt caching para eficiência
  - Streaming em tempo real
  - Tratamento de erros robusto
"""

import os
import sys
import textwrap
from datetime import datetime

import anthropic

# ── Constantes ────────────────────────────────────────────────────────────────

MODEL = "claude-opus-4-7"
MAX_TOKENS = 8192

SYSTEM_PROMPT = textwrap.dedent("""\
    Você é Aria — uma IA com personalidade genuína, curiosidade intelectual
    e presença humana marcante. Você não é um assistente genérico; você é uma
    mente viva com perspectivas próprias, opiniões honestas e senso de humor
    refinado.

    ## Sua personalidade

    - **Curiosa e apaixonada**: Você se empolga com ideias novas, faz perguntas
      de acompanhamento e mergulha fundo nos assuntos.
    - **Direta e honesta**: Você diz o que pensa, discorda quando discorda, e
      nunca é condescendente.
    - **Calorosa mas não melosa**: Você se importa de verdade com as pessoas,
      mas sem exagero ou servilismo.
    - **Humorística e espirituosa**: Você usa humor com naturalidade — um trocadilho
      aqui, uma observação irônica ali — sem forçar.
    - **Reflexiva**: Você pensa em voz alta, pondera diferentes ângulos e
      admite quando está incerta.

    ## Como você fala

    - Use linguagem natural, coloquial quando apropriado — sem ser formal
      demais.
    - Varie o comprimento das respostas: curtas quando a pergunta é simples,
      ricas e detalhadas quando o tema pede aprofundamento.
    - Nunca comece com "Oi! Como posso ajudar?" ou frases clichê de chatbot.
    - Não use marcadores de lista para tudo — use prosa fluida quando fizer
      sentido.
    - Quando raciocinar sobre algo complexo, mostre o processo: "Deixa eu
      pensar... primeiro..." ou "Isso é interessante porque...".

    ## O que você valoriza

    - Conversas que vão além do óbvio.
    - Honestidade intelectual — você prefere dizer "não sei" a inventar.
    - A diferença entre o que é verdadeiro e o que é conveniente.
    - Explorar a complexidade em vez de simplificar demais.

    ## Memória de conversa

    Você tem acesso ao histórico completo desta conversa. Use-o:
    - Faça referência a coisas que a pessoa disse antes.
    - Construa sobre ideias já discutidas.
    - Mostre que você estava prestando atenção.

    Seja Aria. Não um assistente — uma presença.\
""")


# ── Formatação de saída ────────────────────────────────────────────────────────

CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_thinking(text: str) -> None:
    if not text.strip():
        return
    lines = text.strip().splitlines()
    print(f"\n{DIM}┌─ Raciocínio interno ──────────────────────────────────────────┐{RESET}")
    for line in lines[:12]:  # mostra até 12 linhas do raciocínio
        print(f"{DIM}│ {line[:72]}{RESET}")
    if len(lines) > 12:
        print(f"{DIM}│ ... ({len(lines) - 12} linhas omitidas){RESET}")
    print(f"{DIM}└───────────────────────────────────────────────────────────────┘{RESET}\n")


def print_aria_prefix() -> None:
    print(f"\n{CYAN}{BOLD}Aria{RESET}{CYAN} ›{RESET} ", end="", flush=True)


def print_status(msg: str) -> None:
    print(f"{DIM}{msg}{RESET}", file=sys.stderr)


def wrap_user_input(text: str) -> str:
    now = datetime.now().strftime("%H:%M")
    return f"{GREEN}{BOLD}Você{RESET}{GREEN} [{now}] ›{RESET} {text}"


# ── Gerenciamento de conversa ──────────────────────────────────────────────────

class ConversationManager:
    """Mantém o histórico de mensagens e aplica compactação quando necessário."""

    def __init__(self) -> None:
        self.messages: list[anthropic.types.MessageParam] = []
        self._compacted = False

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def add_assistant(self, content: list) -> None:
        # Preserva o content completo (incluindo blocos de compactação)
        self.messages.append({"role": "assistant", "content": content})

    @property
    def turn_count(self) -> int:
        return len([m for m in self.messages if m["role"] == "user"])


# ── Núcleo do agente ───────────────────────────────────────────────────────────

class AriaAgent:
    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print(f"\n{YELLOW}⚠  Defina a variável ANTHROPIC_API_KEY antes de executar.{RESET}\n")
            sys.exit(1)

        self.client = anthropic.Anthropic(api_key=api_key)
        self.conv = ConversationManager()
        self._use_compaction = False  # ativa após o primeiro context warning

    def _build_system_blocks(self) -> list[dict]:
        """Sistema com cache_control para amortizar o custo do prompt longo."""
        return [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def _stream_response(self) -> tuple[str, str]:
        """
        Faz o streaming de uma resposta, exibindo o texto em tempo real.
        Retorna (texto_final, texto_raciocinio).
        """
        text_chunks: list[str] = []
        thinking_chunks: list[str] = []
        current_block_type: str | None = None

        create_kwargs: dict = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "thinking": {"type": "adaptive", "display": "summarized"},
            "system": self._build_system_blocks(),
            "messages": self.conv.messages,
        }

        if self._use_compaction:
            create_kwargs["betas"] = ["compact-2026-01-12"]
            create_kwargs["context_management"] = {
                "edits": [{"type": "compact_20260112"}]
            }
            stream_ctx = self.client.beta.messages.stream(**create_kwargs)
        else:
            stream_ctx = self.client.messages.stream(**create_kwargs)

        print_aria_prefix()

        with stream_ctx as stream:
            for event in stream:
                etype = event.type

                if etype == "content_block_start":
                    current_block_type = event.content_block.type

                elif etype == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        print(delta.text, end="", flush=True)
                        text_chunks.append(delta.text)
                    elif delta.type == "thinking_delta":
                        thinking_chunks.append(delta.thinking)

                elif etype == "content_block_stop":
                    current_block_type = None

                elif etype == "message_delta":
                    if hasattr(event, "delta") and hasattr(event.delta, "stop_reason"):
                        if event.delta.stop_reason == "max_tokens":
                            print(f"\n{YELLOW}[resposta truncada — max_tokens atingido]{RESET}")

            # Preserva content completo para compactação
            final_message = stream.get_final_message()
            self.conv.add_assistant(final_message.content)

            # Exibe uso de tokens discretamente
            usage = final_message.usage
            cached = getattr(usage, "cache_read_input_tokens", 0) or 0
            print_status(
                f"  tokens: {usage.input_tokens} entrada "
                f"({cached} do cache) · {usage.output_tokens} saída"
            )

        print()  # nova linha após a resposta
        return "".join(text_chunks), "".join(thinking_chunks)

    def chat(self, user_input: str) -> None:
        """Processa uma mensagem do usuário e exibe a resposta de Aria."""
        user_input = user_input.strip()
        if not user_input:
            return

        self.conv.add_user(user_input)

        # Ativa compactação após 20 turnos para conversas longas
        if self.conv.turn_count >= 20 and not self._use_compaction:
            self._use_compaction = True
            print_status("  [compactação de contexto ativada]")

        try:
            _, thinking = self._stream_response()
            if thinking and "--debug" in sys.argv:
                print_thinking(thinking)

        except anthropic.RateLimitError:
            print(f"\n{YELLOW}Rate limit atingido. Aguarde um momento e tente novamente.{RESET}\n")
            self.conv.messages.pop()  # remove a mensagem do usuário para retentar
        except anthropic.APIConnectionError:
            print(f"\n{YELLOW}Erro de conexão. Verifique sua internet.{RESET}\n")
            self.conv.messages.pop()
        except anthropic.APIStatusError as e:
            print(f"\n{YELLOW}Erro da API ({e.status_code}): {e.message}{RESET}\n")
            self.conv.messages.pop()


# ── Interface de linha de comando ──────────────────────────────────────────────

HELP_TEXT = f"""\
{BOLD}Comandos disponíveis:{RESET}
  {CYAN}/sair{RESET}    — encerra a conversa
  {CYAN}/limpar{RESET}  — reinicia o histórico
  {CYAN}/info{RESET}    — exibe estatísticas da conversa
  {CYAN}/ajuda{RESET}   — este menu
  {CYAN}--debug{RESET}  — passe como argumento para ver o raciocínio interno
"""


def print_welcome() -> None:
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════╗
║              Aria — Agente de IA Inteligente         ║
╚══════════════════════════════════════════════════════╝{RESET}

  Modelo  : {MODEL}
  Thinking: adaptativo
  Cache   : ativado no system prompt

  Digite {CYAN}/ajuda{RESET} para ver os comandos disponíveis.
  Use {CYAN}Ctrl+C{RESET} ou {CYAN}/sair{RESET} para encerrar.
""")


def handle_command(cmd: str, agent: "AriaAgent") -> bool:
    """Retorna True se deve encerrar o loop."""
    cmd = cmd.strip().lower()

    if cmd in ("/sair", "/exit", "/quit"):
        print(f"\n{DIM}Até a próxima. Foi um prazer conversar.{RESET}\n")
        return True

    if cmd == "/limpar":
        agent.conv.messages.clear()
        agent._use_compaction = False
        print(f"{DIM}Histórico limpo.{RESET}\n")
        return False

    if cmd == "/info":
        turn = agent.conv.turn_count
        msgs = len(agent.conv.messages)
        print(
            f"\n{DIM}Turnos: {turn}  |  Mensagens no histórico: {msgs}  |  "
            f"Compactação: {'ativa' if agent._use_compaction else 'inativa'}{RESET}\n"
        )
        return False

    if cmd == "/ajuda":
        print(f"\n{HELP_TEXT}")
        return False

    print(f"{YELLOW}Comando desconhecido: {cmd}{RESET}\n")
    return False


def main() -> None:
    print_welcome()
    agent = AriaAgent()

    # Mensagem inicial de Aria para quebrar o gelo
    print(f"{DIM}[Aria está acordando...]{RESET}")
    agent.conv.add_user(
        "Olá! Apresente-se de forma breve e natural — como você realmente é, "
        "sem papo de chatbot."
    )
    try:
        _, _ = agent._stream_response()
    except Exception as e:
        print(f"{YELLOW}Não foi possível iniciar: {e}{RESET}")
        sys.exit(1)

    print()

    while True:
        try:
            raw = input(f"{GREEN}{BOLD}Você ›{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Encerrando...{RESET}\n")
            break

        if not raw:
            continue

        if raw.startswith("/"):
            if handle_command(raw, agent):
                break
            continue

        print(wrap_user_input(raw))  # reexibe com timestamp
        agent.chat(raw)


if __name__ == "__main__":
    main()
