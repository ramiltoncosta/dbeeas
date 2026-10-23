/** Página da coleta: dados, envio de fotos, andamento e fotos. */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Alerta, Botao, Carregando } from '../../components/ui'
import { api, mensagemErro, urlArquivo } from '../../lib/api'
import { BIOMAS, dataBR, type Coleta, type Contagem, type Foto, type Pagina, type ResumoColeta } from '../../lib/coletas'
import Envio from './Envio'
import Exportar from './Exportar'
import FotoModal, { Selo } from './FotoModal'
import MapaDaColeta from './MapaDaColeta'
import { parametrosFiltro, type Filtro } from '../../lib/filtros'
import { FiltrosFotos, GraficoEspecies } from './Resultado'

function Andamento({ c }: { c: Contagem }) {
  const pendentes = c.na_fila + c.processando
  const prontas = c.concluidas + c.erro
  return (
    <div className="rounded-2xl border border-tinta-100 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-bold text-tinta-800">
          {pendentes > 0 ? `Processando: ${prontas} de ${c.total}` : `${c.total} foto(s) na coleta`}
        </h2>
        {pendentes > 0 && <span className="text-xs text-tinta-500">Atualiza sozinho. Pode sair da página.</span>}
      </div>
      {pendentes > 0 && (
        <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-tinta-50" role="progressbar" aria-valuenow={prontas} aria-valuemax={c.total}>
          <div className="h-full bg-tinta-500 transition-all duration-500" style={{ width: `${(prontas / Math.max(c.total, 1)) * 100}%` }} />
        </div>
      )}
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        {[
          ['Identificadas', c.identificadas, 'text-emerald-800'],
          ['Não identificadas', c.nao_identificadas, 'text-tinta-700'],
          ['Na fila', pendentes, 'text-mel-700'],
          ['Com erro', c.erro, 'text-red-700'],
        ].map(([rotulo, valor, cor]) => (
          <div key={rotulo as string} className="rounded-lg bg-tinta-50/60 px-3 py-2">
            <dt className="text-xs text-tinta-500">{rotulo}</dt>
            <dd className={`text-xl font-bold ${cor}`}>{valor}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

function Info({ coleta }: { coleta: Coleta }) {
  const itens = [
    ['Data', dataBR(coleta.data_coleta)],
    ['Local', coleta.municipio ? `${coleta.municipio}${coleta.uf ? `/${coleta.uf}` : ''}` : coleta.uf],
    ['Bioma', coleta.bioma && BIOMAS[coleta.bioma]],
    ['Coletor(a)', coleta.coletor],
    ['Armadilha', coleta.tipo_armadilha],
    ['Isca atrativa', coleta.isca_atrativa],
    ['Ponto no mapa', coleta.local ? `${coleta.local.latitude.toFixed(4)}, ${coleta.local.longitude.toFixed(4)}` : null],
  ].filter(([, v]) => v && v !== '—')
  if (!itens.length && !coleta.descricao) return null
  return (
    <div className="space-y-2">
      {coleta.descricao && <p className="text-sm text-tinta-700">{coleta.descricao}</p>}
      <dl className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
        {itens.map(([k, v]) => (
          <div key={k}>
            <dt className="text-xs text-tinta-500">{k}</dt>
            <dd className="font-medium text-tinta-800">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

export default function DetalheColeta() {
  const { id = '' } = useParams()
  const navegar = useNavigate()
  const cliente = useQueryClient()
  const [fotoAberta, setFotoAberta] = useState<Foto | null>(null)
  const [confirmarExclusao, setConfirmarExclusao] = useState(false)

  const coleta = useQuery({ queryKey: ['coleta', id], queryFn: () => api<Coleta>(`/v1/coletas/${id}`) })

  // Enquanto houver fotos na fila, consulta o andamento a cada 2 segundos
  const progresso = useQuery({
    queryKey: ['progresso', id],
    queryFn: () => api<Contagem>(`/v1/coletas/${id}/progresso`),
    refetchInterval: (q) => (q.state.data && q.state.data.na_fila + q.state.data.processando > 0 ? 2000 : false),
  })

  const [filtro, setFiltro] = useState<Filtro>({ tipo: 'todas' })
  const params = new URLSearchParams({ por_pagina: '500', ...parametrosFiltro(filtro) })
  const fotos = useQuery({
    queryKey: ['fotos', id, params.toString()],
    queryFn: () => api<Pagina<Foto>>(`/v1/coletas/${id}/fotos?${params}`),
    placeholderData: keepPreviousData,
  })

  const resumo = useQuery({
    queryKey: ['resumo', id],
    queryFn: () => api<ResumoColeta>(`/v1/coletas/${id}/resumo`),
  })

  // Quando mais fotos terminam (ou chegam), atualiza a grade e o gráfico
  const prontasAntes = useRef<number | null>(null)
  const prontas = progresso.data ? progresso.data.concluidas + progresso.data.erro + progresso.data.total : null
  useEffect(() => {
    if (prontas !== null && prontasAntes.current !== null && prontas !== prontasAntes.current) {
      cliente.invalidateQueries({ queryKey: ['fotos', id] })
      cliente.invalidateQueries({ queryKey: ['resumo', id] })
      cliente.invalidateQueries({ queryKey: ['mapa'] })
    }
    prontasAntes.current = prontas
  }, [prontas, cliente, id])

  // Se o filtro escolhido ficou vazio (ex.: a última foto daquela espécie foi corrigida), volta para "Todas"
  useEffect(() => {
    if (filtro.tipo === 'especie' && resumo.data && !resumo.data.especies.some((e) => e.id === filtro.id)) {
      setFiltro({ tipo: 'todas' })
    }
  }, [filtro, resumo.data])

  // Abre a foto clicada no mapa (busca os dados completos dela)
  const abrirFoto = (fotoId: string) => {
    api<Foto>(`/v1/fotos/${fotoId}`).then(setFotoAberta).catch(() => {})
  }

  const excluir = useMutation({
    mutationFn: () => api(`/v1/coletas/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      cliente.invalidateQueries({ queryKey: ['coletas'] })
      navegar('/coletas')
    },
  })

  if (coleta.isLoading) return <Carregando />
  if (coleta.error || !coleta.data) return <Alerta>{mensagemErro(coleta.error)}</Alerta>

  const c = coleta.data

  return (
    <div className="space-y-6">
      <div>
        <Link to="/coletas" className="text-sm font-semibold text-tinta-500 hover:text-tinta-800">← Coletas</Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          <h1 className="text-2xl font-bold text-tinta-900">{c.nome}</h1>
          <div className="flex flex-wrap gap-2">
            <Link to={`/coletas/${id}/editar`} className="rounded-lg border border-tinta-100 bg-white px-4 py-2 text-sm font-semibold text-tinta-800 hover:bg-tinta-50">
              Editar
            </Link>
            {confirmarExclusao ? (
              <Botao variante="perigo" className="!py-2" carregando={excluir.isPending} onClick={() => excluir.mutate()}>
                Excluir coleta e fotos
              </Botao>
            ) : (
              <Botao variante="secundario" className="!py-2" onClick={() => setConfirmarExclusao(true)}>Excluir</Botao>
            )}
          </div>
        </div>
        {confirmarExclusao && !excluir.isPending && (
          <p className="mt-2 text-sm text-red-700">
            A coleta e todas as fotos serão apagadas definitivamente.{' '}
            <button className="font-semibold underline" onClick={() => setConfirmarExclusao(false)}>Cancelar</button>
          </p>
        )}
        {excluir.error && <div className="mt-2"><Alerta>{mensagemErro(excluir.error)}</Alerta></div>}
        <div className="mt-4"><Info coleta={c} /></div>
      </div>

      <Envio coletaId={id} />

      {progresso.data && progresso.data.na_fila + progresso.data.processando > 0 && <Andamento c={progresso.data} />}

      {resumo.data && resumo.data.total > 0 && (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="rounded-2xl border border-tinta-100 bg-white p-5 shadow-sm">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-lg font-bold text-tinta-800">Espécies na coleta</h2>
              {resumo.data.revisadas > 0 && (
                <span className="text-xs text-tinta-500">{resumo.data.revisadas} foto(s) revisada(s) por pessoas</span>
              )}
            </div>
            <GraficoEspecies resumo={resumo.data} filtro={filtro} aoFiltrar={setFiltro} />
          </section>
          <MapaDaColeta coletaId={id} identificadas={resumo.data.identificadas} aoAbrirFoto={abrirFoto} />
        </div>
      )}

      {resumo.data && resumo.data.total > 0 && <Exportar coletaId={id} progresso={progresso.data} />}

      {resumo.data && resumo.data.total > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-bold text-tinta-800">Fotos</h2>
          <FiltrosFotos resumo={resumo.data} filtro={filtro} aoFiltrar={setFiltro} />
          {fotos.data && fotos.data.itens.length === 0 && (
            <p className="py-6 text-center text-sm text-tinta-500">Nenhuma foto neste filtro.</p>
          )}
          <ul className={`grid grid-cols-2 gap-3 transition-opacity sm:grid-cols-3 lg:grid-cols-5 ${fotos.isPlaceholderData ? 'opacity-60' : ''}`}>
            {fotos.data?.itens.map((f) => (
              <li key={f.id}>
                <button
                  onClick={() => setFotoAberta(f)}
                  className="group block w-full overflow-hidden rounded-xl border border-tinta-100 bg-white text-left shadow-sm transition hover:border-mel-400"
                >
                  <div className="aspect-[4/3] bg-tinta-50">
                    {f.url_miniatura ? (
                      <img src={urlArquivo(f.url_miniatura)} alt="" loading="lazy" className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full items-center justify-center text-xs text-tinta-300">Gerando miniatura…</div>
                    )}
                  </div>
                  <div className="space-y-1 p-2.5">
                    <p className="truncate text-sm font-semibold italic text-tinta-800">
                      {f.especie ?? <span className="not-italic text-tinta-500">{f.nome_original}</span>}
                    </p>
                    <Selo foto={f} />
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {fotoAberta && (
        <FotoModal key={fotoAberta.id} foto={fotoAberta} localColeta={c.local} aoFechar={() => setFotoAberta(null)} />
      )}
    </div>
  )
}
