/** Ficha de uma espécie (aberta ao público). O texto é editado pelo administrador. */
import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import Asa from '../../components/Asa'
import TextoFormatado, { TextoEmLinha } from '../../components/TextoFormatado'
import { Alerta, Carregando } from '../../components/ui'
import { api, mensagemErro, urlArquivo } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import type { EspecieDetalhe } from '../../lib/especies'

function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="font-display text-xl font-bold text-tinta-900">{titulo}</h2>
      <div className="mt-2 leading-relaxed text-tinta-800">{children}</div>
    </section>
  )
}

function NaPlataforma({ e }: { e: EspecieDetalhe }) {
  const { usuario } = useAuth()
  const est = e.estatisticas
  const maior = Math.max(1, ...est.estados.map((x) => x.ocorrencias))
  const anos =
    est.primeiro_ano && est.ultimo_ano
      ? est.primeiro_ano === est.ultimo_ano
        ? `em ${est.primeiro_ano}`
        : `de ${est.primeiro_ano} a ${est.ultimo_ano}`
      : null
  return (
    <aside className="space-y-4 self-start rounded-2xl border border-tinta-100 bg-white p-5 text-sm">
      <h2 className="font-bold text-tinta-800">Registros no DBeeAS</h2>
      {est.ocorrencias === 0 ? (
        <p className="text-tinta-500">Ainda não há registros desta espécie nas coletas compartilhadas no mapa.</p>
      ) : (
        <>
          <p className="text-tinta-700">
            <span className="text-2xl font-bold tabular-nums text-tinta-900">{est.ocorrencias.toLocaleString('pt-BR')}</span>{' '}
            foto(s) em {est.coletas} coleta(s){anos && `, ${anos}`}.
          </p>
          {est.estados.length > 0 && (
            <ul className="space-y-1.5" aria-label="Registros por estado">
              {est.estados.map((uf) => (
                <li key={uf.uf} className="grid grid-cols-[7.5rem_1fr_auto] items-center gap-2" title={`${uf.nome}: ${uf.ocorrencias}`}>
                  <span className="truncate text-tinta-700">{uf.nome}</span>
                  <span className="h-2.5">
                    <span className="block h-full rounded-r bg-mel-500" style={{ width: `${Math.max((uf.ocorrencias / maior) * 100, 3)}%` }} />
                  </span>
                  <span className="tabular-nums text-tinta-500">{uf.ocorrencias}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {e.sensivel && (
        <p className="rounded-lg bg-tinta-50 px-3 py-2 text-xs text-tinta-700">
          Espécie sensível: no mapa, a localização exata fica protegida e aparece só uma área aproximada.
        </p>
      )}
      {usuario ? (
        <Link to={`/mapa?escopo=todas&especie=${e.id}`} className="inline-block font-semibold text-tinta-700 underline">
          Ver no mapa
        </Link>
      ) : (
        <p className="text-xs text-tinta-500">
          <Link to="/cadastrar" className="font-semibold text-tinta-700 underline">Crie uma conta</Link> para ver o mapa de
          ocorrências e identificar suas próprias fotos.
        </p>
      )}
      <p className="text-xs text-tinta-500">Contam só as coletas que os usuários deixaram visíveis no mapa geral.</p>
    </aside>
  )
}

export default function FichaEspecie() {
  const { id = '' } = useParams()
  const dados = useQuery({
    queryKey: ['publico', 'especie', id],
    queryFn: () => api<EspecieDetalhe>(`/v1/publico/especies/${id}`),
  })

  if (dados.isLoading) return <Carregando />
  if (dados.error || !dados.data) {
    return (
      <div className="space-y-4">
        <Alerta>{mensagemErro(dados.error)}</Alerta>
        <Link to="/especies" className="font-semibold text-tinta-700 underline">Ver todas as espécies</Link>
      </div>
    )
  }
  const e = dados.data
  const f = e.ficha

  return (
    <article className="space-y-8">
      <div>
        <Link to="/especies" className="text-sm font-semibold text-tinta-500 hover:text-tinta-800">← Espécies</Link>
        <header className="mt-3">
          <h1 className="font-display text-4xl font-bold italic leading-tight text-tinta-900 sm:text-5xl">{e.nome_cientifico}</h1>
          {(f?.autoria || f?.nome_popular) && (
            <p className="mt-2 text-lg text-tinta-500">
              {f.autoria}
              {f.autoria && f.nome_popular && ', '}
              {f.nome_popular}
            </p>
          )}
        </header>
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="max-w-[68ch] space-y-8">
          <figure>
            <div className="flex aspect-[16/9] items-center justify-center overflow-hidden rounded-2xl border border-tinta-100 bg-white">
              {f?.url_imagem ? (
                <img src={urlArquivo(f.url_imagem)} alt={`Asa de ${e.nome_cientifico}`} className="h-full w-full object-contain" />
              ) : (
                <Asa className="w-3/4 opacity-50" />
              )}
            </div>
            {f?.credito_imagem && <figcaption className="mt-2 text-xs text-tinta-500">{f.credito_imagem}</figcaption>}
          </figure>

          {f ? (
            <>
              {f.descricao && <Secao titulo="Descrição"><TextoFormatado texto={f.descricao} /></Secao>}
              {f.caracteristicas && <Secao titulo="Características"><TextoFormatado texto={f.caracteristicas} /></Secao>}
              {f.distribuicao && <Secao titulo="Distribuição"><TextoFormatado texto={f.distribuicao} /></Secao>}
              {f.fontes && (
                <Secao titulo="Fontes">
                  <ol className="list-decimal space-y-1 pl-5 text-sm">
                    {f.fontes.split('\n').filter((l) => l.trim()).map((l, i) => (
                      <li key={i}><TextoEmLinha texto={l.trim()} /></li>
                    ))}
                  </ol>
                </Secao>
              )}
              {f.atualizado_em && (
                <p className="text-xs text-tinta-500">
                  Atualizada em {new Date(f.atualizado_em).toLocaleDateString('pt-BR')}.
                </p>
              )}
            </>
          ) : (
            <p className="rounded-2xl border border-dashed border-tinta-300 p-5 text-tinta-700">
              A ficha desta espécie está sendo escrita por especialistas. Enquanto isso, você já pode identificá-la
              pelas fotos da asa.
            </p>
          )}
        </div>
        <NaPlataforma e={e} />
      </div>
    </article>
  )
}
