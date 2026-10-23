/**
 * Painel: o resumo das coletas e fotos de quem está logado.
 *
 * - Números principais (coletas, fotos, espécies, fotos no mês).
 * - Espécies encontradas em todas as coletas (uma barra por espécie, com o número escrito ao lado).
 * - Fotos que vale conferir: identificadas com confiança baixa e sem revisão.
 * - Últimas coletas.
 * - Para o administrador, os números da plataforma.
 */
import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Alerta, Carregando } from '../components/ui'
import { api, mensagemErro } from '../lib/api'
import { useAuth } from '../lib/auth'
import { dataBR, type Coleta } from '../lib/coletas'

interface DadosPainel {
  totais: {
    coletas: number
    fotos: number
    identificadas: number
    nao_identificadas: number
    em_processamento: number
    com_erro: number
    revisadas: number
    especies: number
    fotos_mes: number
  }
  especies: { id: number; nome: string; quantidade: number; porcentagem: number; coletas: number }[]
  ultimas_coletas: Coleta[]
  para_revisar: number
  para_revisar_coletas: { id: string; nome: string; fotos: number }[]
  limite_confianca_revisao: number
  plataforma: {
    usuarios: number
    usuarios_novos_30d: number
    coletas: number
    fotos: number
    fotos_hoje: number
    na_fila: number
    com_erro: number
    mensagens_nao_respondidas: number
  } | null
}

const num = (n: number) => n.toLocaleString('pt-BR')

function Numero({ valor, rotulo, detalhe }: { valor: number; rotulo: string; detalhe?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-tinta-100 bg-white px-5 py-4">
      <dt className="text-sm text-tinta-500">{rotulo}</dt>
      <dd className="mt-1 text-3xl font-bold tabular-nums text-tinta-900">{num(valor)}</dd>
      {detalhe && <dd className="mt-1 text-xs text-tinta-500">{detalhe}</dd>}
    </div>
  )
}

function Especies({ dados }: { dados: DadosPainel }) {
  const { especies, totais } = dados
  if (!especies.length) {
    return <p className="text-sm text-tinta-500">As espécies aparecem aqui quando as primeiras fotos forem identificadas.</p>
  }
  const maior = especies[0].quantidade
  return (
    <figure>
      <figcaption className="mb-3 text-xs text-tinta-500">
        Somando todas as coletas. Porcentagens sobre as {num(totais.identificadas)} foto(s) identificada(s)
        {totais.nao_identificadas > 0 && `; as ${num(totais.nao_identificadas)} não identificada(s) ficam de fora`}.
      </figcaption>
      <ul className="space-y-1.5">
        {especies.map((e) => {
          const dica = `${e.nome}: ${e.quantidade} foto(s), ${e.porcentagem.toLocaleString('pt-BR')}%, em ${e.coletas} coleta(s)`
          return (
            <li key={e.id} title={dica} aria-label={dica} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 sm:grid-cols-[minmax(0,13rem)_1fr_auto]">
              <Link to={`/especies/${e.id}`} className="truncate text-sm font-semibold italic text-tinta-800 hover:underline">
                {e.nome}
              </Link>
              <span className="order-last col-span-2 h-3 sm:order-none sm:col-span-1">
                <span className="block h-full rounded-r bg-mel-500" style={{ width: `${Math.max((e.quantidade / maior) * 100, 2)}%` }} />
              </span>
              <span className="whitespace-nowrap text-right text-sm tabular-nums text-tinta-700">
                <span className="font-semibold">{e.porcentagem.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%</span>
                <span className="text-tinta-500"> · {num(e.quantidade)}</span>
              </span>
            </li>
          )
        })}
      </ul>
    </figure>
  )
}

function PrimeirosPassos() {
  const passos = [
    ['Crie uma coleta', 'Dê um nome à saída de campo e, se quiser, informe local, armadilha e isca.', '/coletas/nova'],
    ['Envie as fotos das asas', 'Arraste várias de uma vez. A localização e a data são lidas das fotos.', null],
    ['Confira o resultado', 'Veja as espécies, corrija o que for preciso, abra o mapa e baixe a planilha.', null],
  ] as const
  return (
    <section className="rounded-2xl border border-mel-200 bg-mel-50 p-6">
      <h2 className="text-lg font-bold text-tinta-900">Comece pela sua primeira coleta</h2>
      <ol className="mt-4 grid gap-4 sm:grid-cols-3">
        {passos.map(([titulo, texto], i) => (
          <li key={titulo} className="flex gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-tinta-700 text-sm font-bold text-white">{i + 1}</span>
            <span>
              <span className="block font-semibold text-tinta-800">{titulo}</span>
              <span className="text-sm text-tinta-700">{texto}</span>
            </span>
          </li>
        ))}
      </ol>
      <div className="mt-5 flex flex-wrap gap-3">
        <Link to="/coletas/nova" className="rounded-lg bg-tinta-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-tinta-800">
          Criar coleta
        </Link>
        <Link to="/identificar" className="rounded-lg border border-tinta-100 bg-white px-4 py-2.5 text-sm font-semibold text-tinta-800 hover:bg-tinta-50">
          Só identificar algumas fotos
        </Link>
      </div>
    </section>
  )
}

function Plataforma({ p }: { p: NonNullable<DadosPainel['plataforma']> }) {
  const itens: [string, number, string?][] = [
    ['Usuários', p.usuarios, `${num(p.usuarios_novos_30d)} nos últimos 30 dias`],
    ['Coletas', p.coletas],
    ['Fotos', p.fotos, `${num(p.fotos_hoje)} hoje`],
    ['Na fila agora', p.na_fila],
    ['Fotos com erro', p.com_erro],
  ]
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-bold text-tinta-800">Plataforma</h2>
        <Link to="/admin/mensagens" className="text-sm font-semibold text-tinta-700 underline">
          {p.mensagens_nao_respondidas > 0
            ? `${p.mensagens_nao_respondidas} mensagem(ns) de contato sem resposta`
            : 'Mensagens de contato'}
        </Link>
      </div>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {itens.map(([r, v, d]) => (
          <Numero key={r} rotulo={r} valor={v} detalhe={d} />
        ))}
      </dl>
    </section>
  )
}

export default function Painel() {
  const { usuario } = useAuth()
  const dados = useQuery({
    queryKey: ['painel'],
    queryFn: () => api<DadosPainel>('/v1/painel'),
    // Enquanto houver fotos processando, atualiza sozinho
    refetchInterval: (q) => (q.state.data?.totais.em_processamento ? 5000 : false),
  })
  if (!usuario) return null
  const primeiroNome = usuario.nome.split(' ')[0]
  const d = dados.data

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-tinta-900">Olá, {primeiroNome}!</h1>
          <p className="mt-1 text-tinta-500">Suas coletas e identificações em um só lugar.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/coletas/nova" className="rounded-lg bg-tinta-700 px-4 py-2 text-sm font-semibold text-white hover:bg-tinta-800">
            Nova coleta
          </Link>
          <Link to="/identificar" className="rounded-lg border border-tinta-100 bg-white px-4 py-2 text-sm font-semibold text-tinta-800 hover:bg-tinta-50">
            Identificar fotos
          </Link>
        </div>
      </div>

      {usuario.perfil === 'pesquisador' && !usuario.perfil_aprovado && (
        <Alerta tipo="info">
          Seu perfil de pesquisador está aguardando aprovação. Enquanto isso, você já pode usar o sistema
          normalmente; só a localização exata de espécies sensíveis fica oculta.
        </Alerta>
      )}

      {dados.isLoading && <Carregando />}
      {dados.error && <Alerta>{mensagemErro(dados.error)}</Alerta>}

      {d && (
        <>
          {d.totais.coletas === 0 && <PrimeirosPassos />}

          {d.totais.coletas > 0 && (
            <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Numero rotulo="Coletas" valor={d.totais.coletas} />
              <Numero
                rotulo="Fotos"
                valor={d.totais.fotos}
                detalhe={
                  d.totais.em_processamento > 0
                    ? `${num(d.totais.em_processamento)} em processamento`
                    : `${num(d.totais.identificadas)} identificada(s)`
                }
              />
              <Numero rotulo="Espécies encontradas" valor={d.totais.especies} />
              <Numero
                rotulo="Fotos neste mês"
                valor={d.totais.fotos_mes}
                detalhe={d.totais.revisadas > 0 ? `${num(d.totais.revisadas)} revisada(s) no total` : undefined}
              />
            </dl>
          )}

          {d.para_revisar > 0 && (
            <section className="rounded-2xl border border-mel-200 bg-mel-50 p-5">
              <h2 className="font-bold text-tinta-900">{num(d.para_revisar)} foto(s) para conferir</h2>
              <p className="mt-1 text-sm text-tinta-700">
                O modelo identificou com confiança abaixo de {Math.round(d.limite_confianca_revisao * 100)}% e ninguém
                revisou ainda. Confirmar ou corrigir deixa seus dados mais confiáveis e ajuda a melhorar o modelo.
              </p>
              <ul className="mt-3 flex flex-wrap gap-2">
                {d.para_revisar_coletas.map((c) => (
                  <li key={c.id}>
                    <Link
                      to={`/coletas/${c.id}?filtro=para_revisar`}
                      className="inline-block rounded-full border border-mel-400 bg-white px-3 py-1 text-sm font-semibold text-tinta-800 hover:bg-mel-100"
                    >
                      {c.nome} <span className="font-normal text-tinta-500">{c.fotos}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {d.totais.coletas > 0 && (
            <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
              <section className="rounded-2xl border border-tinta-100 bg-white p-5">
                <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                  <h2 className="text-lg font-bold text-tinta-800">Espécies encontradas</h2>
                  <Link to="/mapa" className="text-sm font-semibold text-tinta-700 underline">Ver no mapa</Link>
                </div>
                <Especies dados={d} />
              </section>

              <section className="rounded-2xl border border-tinta-100 bg-white p-5">
                <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                  <h2 className="text-lg font-bold text-tinta-800">Últimas coletas</h2>
                  <Link to="/coletas" className="text-sm font-semibold text-tinta-700 underline">Todas</Link>
                </div>
                <ul className="divide-y divide-tinta-100">
                  {d.ultimas_coletas.map((c) => (
                    <li key={c.id}>
                      <Link to={`/coletas/${c.id}`} className="flex items-center gap-3 py-2.5 hover:bg-tinta-50/60">
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-semibold text-tinta-800">{c.nome}</span>
                          <span className="block truncate text-xs text-tinta-500">
                            {[dataBR(c.data_coleta), c.municipio && `${c.municipio}${c.uf ? `/${c.uf}` : ''}`]
                              .filter((x) => x && x !== '—')
                              .join(', ') || 'Sem data e local'}
                          </span>
                        </span>
                        <span className="whitespace-nowrap text-right text-sm tabular-nums text-tinta-700">
                          {c.fotos.total} foto(s)
                          {c.fotos.na_fila + c.fotos.processando > 0 && (
                            <span className="block text-xs text-mel-700">processando</span>
                          )}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          )}

          {d.plataforma && <Plataforma p={d.plataforma} />}
        </>
      )}
    </div>
  )
}
