/** Meu plano: situação da assinatura, uso do mês e pedido de outro plano. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Alerta, Botao, Carregando } from '../components/ui'
import { api, mensagemErro } from '../lib/api'
import { COR_STATUS, dataCurta, limiteTexto, NOMES_STATUS, preco, useMeuPlano, type Assinatura, type Plano } from '../lib/planos'

function Uso({ usadas, limite, fotos, rapidas }: { usadas: number; limite: number | null; fotos: number; rapidas: number }) {
  const fracao = limite ? Math.min(usadas / limite, 1) : 0
  const mes = new Date().toLocaleDateString('pt-BR', { month: 'long' })
  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm text-tinta-500">Fotos usadas em {mes}</p>
        <p className="tabular-nums text-tinta-900">
          <span className="text-2xl font-bold">{usadas.toLocaleString('pt-BR')}</span>
          {limite != null && <span className="text-tinta-500"> de {limite.toLocaleString('pt-BR')}</span>}
        </p>
      </div>
      {limite != null && (
        <div
          className="mt-2 h-3 overflow-hidden rounded-full bg-tinta-50"
          role="progressbar"
          aria-valuenow={usadas}
          aria-valuemax={limite}
          aria-label="Uso do mês"
        >
          <div className={`h-full rounded-full ${fracao >= 0.9 ? 'bg-red-700' : 'bg-mel-500'}`} style={{ width: `${Math.max(fracao * 100, usadas ? 2 : 0)}%` }} />
        </div>
      )}
      <p className="mt-2 text-xs text-tinta-500">
        {fotos.toLocaleString('pt-BR')} em coletas e {rapidas.toLocaleString('pt-BR')} na identificação rápida. O saldo renova
        no dia 1º de cada mês; apagar fotos não devolve o saldo.
      </p>
    </div>
  )
}

function CartaoPlano({ p, atual, pedido, aoPedir, pedindo }: { p: Plano; atual: boolean; pedido: boolean; aoPedir: () => void; pedindo: boolean }) {
  const valor = preco(p.preco_mensal_centavos)
  return (
    <li className={`flex flex-col rounded-2xl border bg-white p-5 ${atual ? 'border-mel-500 ring-1 ring-mel-500' : 'border-tinta-100'}`}>
      <h3 className="font-display text-xl font-bold text-tinta-900">{p.nome}</h3>
      <p className="mt-1 text-sm text-tinta-700">{p.descricao}</p>
      <p className="mt-3 text-tinta-900">
        {valor ? (
          <>
            <span className="text-2xl font-bold">{valor}</span> <span className="text-sm text-tinta-500">por mês</span>
          </>
        ) : (
          <span className="text-sm font-semibold text-tinta-700">Valor sob consulta</span>
        )}
      </p>
      <ul className="mt-3 flex-1 space-y-1 text-sm text-tinta-800">
        <li>{limiteTexto(p.limite_fotos_mes)}</li>
        <li>{p.permite_exportacao ? 'Exportação ZIP e Darwin Core' : 'Sem exportação ZIP'}</li>
      </ul>
      <div className="mt-4">
        {atual ? (
          <span className="text-sm font-semibold text-tinta-700">Seu plano atual</span>
        ) : pedido ? (
          <span className="text-sm font-semibold text-mel-700">Pedido em análise</span>
        ) : (
          <Botao variante="secundario" className="w-full" carregando={pedindo} onClick={aoPedir}>
            Pedir este plano
          </Botao>
        )}
      </div>
    </li>
  )
}

export default function MeuPlano() {
  const cliente = useQueryClient()
  const meu = useMeuPlano()
  const planos = useQuery({ queryKey: ['planos'], queryFn: () => api<Plano[]>('/v1/planos') })
  const [resposta, setResposta] = useState<string | null>(null)

  const pedir = useMutation({
    mutationFn: (plano_id: number) =>
      api<{ mensagem: string; url_pagamento: string | null; pedido: Assinatura }>('/v1/eu/plano/pedido', {
        method: 'POST',
        body: { plano_id },
      }),
    onSuccess: (r) => {
      cliente.invalidateQueries({ queryKey: ['meu-plano'] })
      if (r.url_pagamento) window.location.assign(r.url_pagamento) // serviço de pagamento
      else setResposta(r.mensagem)
    },
  })
  const desistir = useMutation({
    mutationFn: () => api('/v1/eu/plano/pedido', { method: 'DELETE' }),
    onSuccess: () => {
      setResposta(null)
      cliente.invalidateQueries({ queryKey: ['meu-plano'] })
    },
  })

  if (meu.isLoading) return <Carregando />
  if (meu.error || !meu.data) return <Alerta>{mensagemErro(meu.error)}</Alerta>
  const m = meu.data
  const fim = dataCurta(m.assinatura?.fim ?? null)

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-tinta-900">Meu plano</h1>
        <p className="mt-1 text-sm text-tinta-500">Sua assinatura e quantas fotos você já usou neste mês.</p>
      </div>

      <section className="grid gap-6 rounded-2xl border border-tinta-100 bg-white p-6 md:grid-cols-2">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="font-display text-2xl font-bold text-tinta-900">{m.plano?.nome ?? (m.status === 'ilimitado' ? 'Administração' : 'Nenhum plano')}</h2>
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${COR_STATUS[m.status]}`}>{NOMES_STATUS[m.status]}</span>
          </div>
          <p className="mt-2 text-sm text-tinta-700">
            {m.status === 'ilimitado'
              ? 'Contas de administrador não têm limite de fotos.'
              : m.status === 'teste' && fim
                ? `Teste gratuito até ${fim}. Depois disso, peça um plano para continuar enviando fotos.`
                : m.status === 'expirada' && fim
                  ? `Venceu em ${fim}.`
                  : fim
                    ? `Válido até ${fim}.`
                    : m.plano
                      ? 'Sem data de vencimento.'
                      : 'Escolha um plano abaixo para enviar fotos.'}
          </p>
          {m.plano && <p className="mt-1 text-sm text-tinta-500">{limiteTexto(m.plano.limite_fotos_mes)}.</p>}
          {m.motivo_bloqueio && <div className="mt-4"><Alerta>{m.motivo_bloqueio}</Alerta></div>}
        </div>
        <Uso usadas={m.uso.usadas} limite={m.uso.limite} fotos={m.uso.fotos} rapidas={m.uso.identificacoes_rapidas} />
      </section>

      {resposta && <Alerta tipo="sucesso">{resposta}</Alerta>}
      {m.pedido && !resposta && (
        <Alerta tipo="info">
          Você pediu o plano <strong>{m.pedido.plano.nome}</strong> em {dataCurta(m.pedido.criado_em)}. A equipe do DBeeAS vai
          entrar em contato pelo seu e-mail para ativar. Enquanto isso, o plano atual continua valendo.{' '}
          <button className="font-semibold underline" disabled={desistir.isPending} onClick={() => desistir.mutate()}>
            Desistir do pedido
          </button>
        </Alerta>
      )}
      {(pedir.error || desistir.error) && <Alerta>{mensagemErro(pedir.error ?? desistir.error)}</Alerta>}

      {m.status !== 'ilimitado' && (
        <section className="space-y-4">
          <h2 className="text-lg font-bold text-tinta-800">Planos</h2>
          <ul className="grid gap-4 md:grid-cols-3">
            {planos.data?.map((p) => (
              <CartaoPlano
                key={p.id}
                p={p}
                atual={p.id === m.plano?.id && m.status === 'ativa'}
                pedido={p.id === m.pedido?.plano.id}
                pedindo={pedir.isPending && pedir.variables === p.id}
                aoPedir={() => pedir.mutate(p.id)}
              />
            ))}
          </ul>
          <p className="text-xs text-tinta-500">
            Ainda não há cobrança automática: depois do pedido, a equipe envia as instruções de pagamento e ativa o plano.
          </p>
        </section>
      )}
    </div>
  )
}
