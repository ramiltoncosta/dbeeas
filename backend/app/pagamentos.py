"""Interface de pagamento (abstrata).

O DBeeAS ainda não cobra automaticamente. Esta interface define o que qualquer
serviço de pagamento precisa fazer, para que integrar o Asaas, o Mercado Pago ou o
Pagar.me depois seja só escrever uma classe nova, sem mexer no resto do sistema:

    class GatewayAsaas:
        nome = "asaas"
        def iniciar_assinatura(...): cria o cliente e a assinatura no Asaas e
            devolve o link de pagamento
        def cancelar_assinatura(...): cancela no Asaas
        def ler_webhook(...): confere o token do Asaas e traduz o aviso
            ("PAYMENT_CONFIRMED", "PAYMENT_OVERDUE"...) num EventoPagamento

e registrar em GATEWAYS. O serviço em uso é escolhido pela variável
GATEWAY_PAGAMENTO. Hoje é "manual": o pedido fica registrado e o administrador
ativa o plano pelo site.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.emails import enviar_email
from app.models import Assinatura, Plano, StatusAssinatura, Usuario
from app.security import agora

log = logging.getLogger("dbeeas.pagamentos")

# Quanto tempo um pagamento mensal confirmado libera
PERIODO_PAGO = timedelta(days=31)


@dataclass
class Cobranca:
    """Resposta ao pedir um plano."""

    mensagem: str
    codigo_externo: str | None = None  # identificador da assinatura no serviço de pagamento
    url_pagamento: str | None = None  # página do serviço para a pessoa pagar


@dataclass
class EventoPagamento:
    """Aviso do serviço de pagamento, já traduzido."""

    codigo_externo: str
    tipo: Literal["pago", "atrasado", "cancelado"]


class AssinaturaInvalida(Exception):
    """O aviso não veio do serviço de pagamento (assinatura ou token errado)."""


class GatewayPagamento(Protocol):
    nome: str

    def iniciar_assinatura(self, usuario: Usuario, plano: Plano, pedido_id: str) -> Cobranca: ...

    def cancelar_assinatura(self, codigo_externo: str) -> None: ...

    def ler_webhook(self, cabecalhos: dict[str, str], corpo: bytes) -> EventoPagamento | None:
        """Confere a autenticidade e traduz. None = aviso que não interessa."""
        ...


class GatewayManual:
    """Sem cobrança automática: avisa a equipe, que ativa o plano pelo site."""

    nome = "manual"

    def iniciar_assinatura(self, usuario: Usuario, plano: Plano, pedido_id: str) -> Cobranca:
        enviar_email(
            get_settings().email_contato,
            f"DBeeAS – Pedido de plano {plano.nome}: {usuario.nome}",
            f"{usuario.nome} ({usuario.email}) pediu o plano {plano.nome}.\n\n"
            "Ative em Administração > Usuários.\n",
        )
        return Cobranca(
            mensagem=f"Pedido do plano {plano.nome} recebido. A equipe do DBeeAS vai entrar em "
            "contato pelo seu e-mail com as instruções de pagamento e ativar o plano."
        )

    def cancelar_assinatura(self, codigo_externo: str) -> None:
        return None

    def ler_webhook(self, cabecalhos: dict[str, str], corpo: bytes) -> EventoPagamento | None:
        raise AssinaturaInvalida("O modo manual não recebe avisos de pagamento.")


GATEWAYS: dict[str, type] = {"manual": GatewayManual}


def get_gateway() -> GatewayPagamento:
    nome = get_settings().gateway_pagamento
    if nome not in GATEWAYS:
        raise RuntimeError(f"GATEWAY_PAGAMENTO desconhecido: {nome}")
    return GATEWAYS[nome]()


def aplicar_evento(db: Session, gateway: str, evento: EventoPagamento) -> Assinatura | None:
    """Atualiza a assinatura conforme o aviso do serviço de pagamento.

    Cada aviso cria uma linha nova no histórico (nada é sobrescrito).
    """
    ultima = db.scalar(
        select(Assinatura)
        .where(Assinatura.origem == gateway, Assinatura.codigo_externo == evento.codigo_externo)
        .order_by(Assinatura.criado_em.desc())
        .limit(1)
    )
    if ultima is None:
        log.warning("Aviso de pagamento para assinatura desconhecida: %s", evento.codigo_externo)
        return None

    if evento.tipo == "pago":
        # Soma o período ao prazo atual (pagar adiantado não perde dias)
        base = ultima.fim if ultima.fim and ultima.fim > agora() else agora()
        status, fim = StatusAssinatura.ativa, base + PERIODO_PAGO
    elif evento.tipo == "atrasado":
        status, fim = StatusAssinatura.suspensa, ultima.fim
    else:
        status, fim = StatusAssinatura.cancelada, agora()

    nova = Assinatura(
        usuario_id=ultima.usuario_id,
        plano_id=ultima.plano_id,
        status=status,
        fim=fim,
        origem=gateway,
        codigo_externo=evento.codigo_externo,
        observacao=f"Aviso do serviço de pagamento: {evento.tipo}",
    )
    db.add(nova)
    db.commit()
    return nova
