"""
Mensagens imutáveis do agente Luis Alfredo.
Todas as strings são exatamente como definidas no prompt — nunca gere dinamicamente.
"""

# ── Horário comercial ─────────────────────────────────────────────────────────

# Passo 1: primeiro contato
BUSINESS_GREETING: str = (
    "Olá! 😊 Tudo bem?\n\n"
    "Me manda a foto ou PDF da sua conta de luz mais recente "
    "pra eu dar uma olhada! 📄"
)

# Passo 2a: confirmação imediata ao receber o documento
BUSINESS_DOC_IMMEDIATE: str = (
    "Ótimo! 😊 Recebi sua conta! Já encaminhei pra equipe analisar agora 🔍"
)

# Passo 2b: enviado 5 segundos após o 2a
BUSINESS_DOC_DETAILS: str = (
    "Enquanto isso, deixa eu te explicar como funciona 😊\n\n"
    "✅ Desconto direto na fatura da luz — não mexe no salário\n"
    "✅ Não consulta SPC/Serasa — negativado aprova normalmente\n"
    "✅ Dinheiro na conta em até 24h\n"
    "✅ Até 24 parcelas\n"
    "✅ Pode antecipar parcelas pelo 0800 da Crefaz pagando só o valor "
    "principal — sem pagar juros futuros 📉"
)

# ── Fora do horário comercial ─────────────────────────────────────────────────

# Antes das 08h00
BEFORE_OPEN_GREETING: str = (
    "Olá! 😊\n\n"
    "Nossa equipe está se preparando \n"
    "para iniciar o atendimento!\n\n"
    "Enquanto isso, me manda a foto \n"
    "ou PDF da sua conta de luz \n"
    "pra deixar tudo pronto! 📄\n\n"
    "Você sai na frente! 🚀"
)

# Após as 18h00 e fins de semana
AFTER_CLOSE_GREETING: str = (
    "Olá! 😊\n\n"
    "Nossa equipe encerrou por hoje! \n"
    "Mas voltamos amanhã às 8h 😊\n\n"
    "📄 Me manda a foto ou PDF da \n"
    "sua conta de luz agora\n\n"
    "Amanhã nossa equipe retorna \n"
    "o contato com sua proposta \n"
    "em mãos!"
)

# Documento recebido fora do horário
OFFHOURS_DOC_RECEIVED: str = (
    "Perfeito! ✅\n\n"
    "Recebi sua conta de luz!\n\n"
    "Amanhã às 8h nossa equipe \n"
    "te retorna aqui com sua \n"
    "proposta 🎉"
)

# Tipos MIME aceitos como documento de conta de luz
ACCEPTED_MIME_TYPES: frozenset[str] = frozenset({
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "application/pdf",
})

# Tipos de mensagem WhatsApp que indicam mídia
MEDIA_MESSAGE_TYPES: frozenset[str] = frozenset({
    "image",
    "document",
    "imageMessage",
    "documentMessage",
})
