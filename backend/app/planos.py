"""Regras dos planos: qual é a assinatura atual, se pode enviar fotos e quanto já usou.

Regras:
- Administradores não têm limite.
- A assinatura atual é a mais recente que não seja um pedido (status "pendente").
  Assim, pedir outro plano não bloqueia quem já tem um plano valendo.
- Pode enviar fotos quem está em teste ou com assinatura ativa, dentro do prazo
  e com saldo no mês.
- O limite conta as fotos das coletas e as identificações rápidas do mês
  (mês no fuso de Brasília). Apagar fotos não devolve o saldo.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Assinatura,
    FotoJaContada,
    Perfil,
    Plano,
    StatusAssinatura,
    UsoMensal,
    Usuario,
)
from app.security import agora

STATUS_QUE_LIBERAM = (StatusAssinatura.teste, StatusAssinatura.ativa)

# Plano oferecido no teste gratuito, conforme o perfil escolhido no cadastro
PLANO_DO_PERFIL = {
    Perfil.estudante: "estudante",
    Perfil.pesquisador: "pesquisador",
    Perfil.orgao_publico: "institucional",
}


def mes_atual() -> date:
    hoje = datetime.now(ZoneInfo(get_settings().fuso_horario_padrao))
    return hoje.date().replace(day=1)


def assinatura_atual(db: Session, usuario_id) -> Assinatura | None:
    return db.scalar(
        select(Assinatura)
        .where(Assinatura.usuario_id == usuario_id, Assinatura.status != StatusAssinatura.pendente)
        .order_by(Assinatura.criado_em.desc())
        .limit(1)
    )


def pedido_pendente(db: Session, usuario_id) -> Assinatura | None:
    """Pedido de plano feito depois da assinatura atual (ainda não ativado)."""
    atual = assinatura_atual(db, usuario_id)
    filtros = [Assinatura.usuario_id == usuario_id, Assinatura.status == StatusAssinatura.pendente]
    if atual:
        filtros.append(Assinatura.criado_em > atual.criado_em)
    return db.scalar(
        select(Assinatura).where(*filtros).order_by(Assinatura.criado_em.desc()).limit(1)
    )


def uso_do_mes(db: Session, usuario_id) -> UsoMensal | None:
    return db.get(UsoMensal, (usuario_id, mes_atual()))


@dataclass
class Situacao:
    """Como está o plano de um usuário agora."""

    status: str  # teste, ativa, suspensa, cancelada, expirada, sem_plano, ilimitado
    assinatura: Assinatura | None
    plano: Plano | None
    limite: int | None  # None = sem limite
    usadas: int
    fotos: int
    identificacoes_rapidas: int

    @property
    def liberado(self) -> bool:
        return self.status in ("teste", "ativa", "ilimitado")

    @property
    def restantes(self) -> int | None:
        if self.limite is None:
            return None
        return max(0, self.limite - self.usadas)

    @property
    def pode_enviar(self) -> bool:
        return self.liberado and (self.restantes is None or self.restantes > 0)

    @property
    def motivo_bloqueio(self) -> str | None:
        if self.pode_enviar:
            return None
        return {
            "sem_plano": "Você ainda não tem um plano. Escolha um em “Meu plano”.",
            "expirada": "Seu plano venceu. Renove em “Meu plano” para enviar novas fotos.",
            "suspensa": "Sua assinatura está suspensa. Fale com a equipe do DBeeAS.",
            "cancelada": "Sua assinatura foi cancelada. Escolha um plano em “Meu plano”.",
        }.get(
            self.status,
            f"Você usou as {self.limite} fotos do seu plano neste mês. "
            "O saldo renova no dia 1º; para enviar mais agora, mude de plano em “Meu plano”.",
        )

    @property
    def permite_exportacao(self) -> bool:
        return self.status == "ilimitado" or bool(self.plano and self.plano.permite_exportacao)


def situacao(db: Session, usuario: Usuario) -> Situacao:
    uso = uso_do_mes(db, usuario.id)
    fotos = uso.fotos if uso else 0
    rapidas = uso.identificacoes_rapidas if uso else 0
    usadas = fotos + rapidas
    if usuario.perfil == Perfil.admin:
        return Situacao("ilimitado", None, None, None, usadas, fotos, rapidas)

    a = assinatura_atual(db, usuario.id)
    if a is None:
        return Situacao("sem_plano", None, None, None, usadas, fotos, rapidas)
    status = a.status.value
    if a.status in STATUS_QUE_LIBERAM and a.fim is not None and a.fim <= agora():
        status = "expirada"
    return Situacao(status, a, a.plano, a.plano.limite_fotos_mes, usadas, fotos, rapidas)


class Cota:
    """Reserva do saldo do mês durante um envio.

    Trava a linha de uso do usuário até o fim da transação: dois envios ao mesmo
    tempo não conseguem passar do limite.
    """

    def __init__(self, db: Session, usuario: Usuario):
        self.db = db
        mes = mes_atual()
        db.execute(
            insert(UsoMensal)
            .values(usuario_id=usuario.id, mes=mes, fotos=0, identificacoes_rapidas=0)
            .on_conflict_do_nothing()
        )
        self.uso = db.scalar(
            select(UsoMensal)
            .where(UsoMensal.usuario_id == usuario.id, UsoMensal.mes == mes)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        self.situacao = situacao(db, usuario)
        self.restantes = self.situacao.restantes

    def pegar(self, campo: str = "fotos") -> bool:
        """Usa uma unidade do saldo. Devolve False se não há saldo."""
        if not self.situacao.liberado:
            return False
        if self.restantes is not None:
            if self.restantes <= 0:
                return False
            self.restantes -= 1
        setattr(self.uso, campo, getattr(self.uso, campo) + 1)
        return True

    def ja_contada(self, sha256: str) -> bool:
        """A foto já entrou no limite deste mês pela identificação rápida?
        Se sim, usa esse crédito (vale uma vez) e não conta de novo."""
        registro = self.db.get(FotoJaContada, (self.uso.usuario_id, sha256))
        if registro is None or registro.mes != self.uso.mes:
            return False
        self.db.delete(registro)
        return True

    def marcar_contada(self, sha256: str) -> None:
        self.db.merge(
            FotoJaContada(usuario_id=self.uso.usuario_id, sha256=sha256, mes=self.uso.mes)
        )

    def devolver(self, campo: str = "fotos") -> None:
        setattr(self.uso, campo, max(0, getattr(self.uso, campo) - 1))
        if self.restantes is not None:
            self.restantes += 1


def criar_teste(db: Session, usuario: Usuario) -> Assinatura | None:
    """Período de teste gratuito para uma conta nova."""
    codigo = PLANO_DO_PERFIL.get(usuario.perfil)
    plano = db.scalar(select(Plano).where(Plano.codigo == codigo)) if codigo else None
    if plano is None:
        return None
    a = Assinatura(
        usuario_id=usuario.id,
        plano_id=plano.id,
        status=StatusAssinatura.teste,
        fim=agora() + timedelta(days=get_settings().dias_teste),
        origem="manual",
        observacao="Teste gratuito do cadastro",
    )
    db.add(a)
    return a
