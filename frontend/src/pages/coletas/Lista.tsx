import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Alerta, Campo, Carregando } from '../../components/ui'
import { api, mensagemErro } from '../../lib/api'
import { BIOMAS, dataBR, type Coleta, type Pagina } from '../../lib/coletas'

export default function ListaColetas() {
  const [busca, setBusca] = useState('')
  const params = new URLSearchParams({ por_pagina: '100' })
  if (busca.trim()) params.set('busca', busca.trim())

  const consulta = useQuery({
    queryKey: ['coletas', params.toString()],
    queryFn: () => api<Pagina<Coleta>>(`/v1/coletas?${params}`),
    placeholderData: keepPreviousData,
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-tinta-900">Coletas</h1>
          <p className="mt-1 text-sm text-tinta-500">Cada coleta reúne as fotos de uma saída de campo.</p>
        </div>
        <Link to="/coletas/nova" className="rounded-lg bg-mel-500 px-4 py-2.5 text-sm font-semibold text-tinta-900 hover:bg-mel-400">
          + Nova coleta
        </Link>
      </div>

      <Campo rotulo="Buscar" placeholder="Nome da coleta ou município" value={busca} onChange={(e) => setBusca(e.target.value)} className="max-w-md" />

      {consulta.error && <Alerta>{mensagemErro(consulta.error)}</Alerta>}
      {consulta.isLoading && <Carregando />}

      {consulta.data && consulta.data.itens.length === 0 && (
        <div className="rounded-2xl border border-dashed border-tinta-100 bg-white px-6 py-12 text-center">
          <p className="font-semibold text-tinta-800">{busca ? 'Nenhuma coleta encontrada.' : 'Você ainda não tem coletas.'}</p>
          {!busca && (
            <p className="mt-1 text-sm text-tinta-500">
              Crie uma coleta e envie as fotos das asas para identificar as espécies.
            </p>
          )}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {consulta.data?.itens.map((c) => {
          const pendentes = c.fotos.na_fila + c.fotos.processando
          return (
            <Link
              key={c.id}
              to={`/coletas/${c.id}`}
              className="group rounded-2xl border border-tinta-100 bg-white p-5 shadow-sm transition hover:border-mel-400 hover:shadow"
            >
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-lg font-bold text-tinta-800 group-hover:text-tinta-900">{c.nome}</h2>
                {pendentes > 0 && (
                  <span className="shrink-0 rounded-full bg-mel-100 px-2.5 py-0.5 text-xs font-semibold text-mel-700">
                    Processando {pendentes}
                  </span>
                )}
              </div>
              <p className="mt-1 text-sm text-tinta-500">
                {[dataBR(c.data_coleta), c.municipio && `${c.municipio}${c.uf ? `/${c.uf}` : ''}`, c.bioma && BIOMAS[c.bioma]]
                  .filter((x) => x && x !== '—')
                  .join(' · ') || 'Sem data e local'}
              </p>
              <dl className="mt-4 flex gap-6 text-sm">
                <div>
                  <dt className="text-xs text-tinta-500">Fotos</dt>
                  <dd className="text-lg font-bold text-tinta-800">{c.fotos.total}</dd>
                </div>
                <div>
                  <dt className="text-xs text-tinta-500">Identificadas</dt>
                  <dd className="text-lg font-bold text-tinta-800">{c.fotos.identificadas}</dd>
                </div>
                {c.fotos.erro > 0 && (
                  <div>
                    <dt className="text-xs text-red-700">Com erro</dt>
                    <dd className="text-lg font-bold text-red-700">{c.fotos.erro}</dd>
                  </div>
                )}
              </dl>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
