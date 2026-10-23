/**
 * Mapa de ocorrências: onde cada espécie foi encontrada.
 *
 * - Pontos próximos são agrupados (número no círculo) e se separam ao aproximar o zoom.
 * - Cores: até 3 espécies ganham cor própria; as demais ficam em cinza ("outras espécies").
 *   Com mais de 3 cores no mapa, fica difícil distinguir os pontos, principalmente para
 *   quem tem daltonismo. Para ver uma espécie específica, use o filtro.
 * - Espécies sensíveis aparecem com localização aproximada (círculo tracejado) para quem
 *   não tem permissão de ver o ponto exato.
 */
import 'leaflet/dist/leaflet.css'
import { useQuery } from '@tanstack/react-query'
import L from 'leaflet'
import { useEffect, useMemo, useState } from 'react'
import { Circle, CircleMarker, MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import { Link, useSearchParams } from 'react-router-dom'
import Supercluster from 'supercluster'
import { Alerta, Campo, Selecao } from '../components/ui'
import { api, mensagemErro, urlArquivo } from '../lib/api'
import { dataBR, type Coleta, type Especie, type Pagina } from '../lib/coletas'

interface Propriedades {
  especie_id: number
  especie: string
  data: string | null
  revisada: boolean
  aproximada: boolean
  raio_km: number | null
  minha: boolean
  foto_id?: string
  coleta_id?: string
  coleta?: string
  url_miniatura?: string | null
}

type Ocorrencia = GeoJSON.Feature<GeoJSON.Point, Propriedades>

// Paleta categórica validada (3 primeiras cores: distinguíveis entre si também com daltonismo)
const CORES = ['#2a78d6', '#eb6834', '#1baf7a']
const COR_OUTRAS = '#8a8f98'
const CENTRO_BRASIL: [number, number] = [-14.2, -51.9]

function coresPorEspecie(ocorrencias: Ocorrencia[]) {
  const contagem = new Map<number, { nome: string; n: number }>()
  for (const o of ocorrencias) {
    const atual = contagem.get(o.properties.especie_id)
    contagem.set(o.properties.especie_id, { nome: o.properties.especie, n: (atual?.n ?? 0) + 1 })
  }
  const lista = [...contagem.entries()].map(([id, v]) => ({ id, ...v }))
  // Com até 3 espécies, a cor segue a espécie (ordem alfabética), não a quantidade
  const ordenada =
    lista.length <= CORES.length
      ? lista.sort((a, b) => a.nome.localeCompare(b.nome))
      : lista.sort((a, b) => b.n - a.n || a.nome.localeCompare(b.nome))
  const cor = new Map<number, string>()
  ordenada.forEach((e, i) => cor.set(e.id, CORES[i] ?? COR_OUTRAS))
  return { cor, legenda: ordenada.map((e) => ({ ...e, cor: cor.get(e.id)! })) }
}

function AjustarZoom({ ocorrencias }: { ocorrencias: Ocorrencia[] }) {
  const mapa = useMap()
  useEffect(() => {
    if (!ocorrencias.length) return
    const limites = L.latLngBounds(ocorrencias.map((o) => [o.geometry.coordinates[1], o.geometry.coordinates[0]]))
    mapa.whenReady(() => {
      mapa.invalidateSize() // garante que o mapa sabe o próprio tamanho antes de enquadrar
      mapa.fitBounds(limites, { padding: [40, 40], maxZoom: 13, animate: false })
    })
  }, [ocorrencias, mapa])
  return null
}

function Pontos({ ocorrencias, cor }: { ocorrencias: Ocorrencia[]; cor: Map<number, string> }) {
  const mapa = useMap()
  // Redesenha quando o mapa muda; o zoom e a área visível são lidos direto do mapa
  const [, setVersao] = useState(0)
  const redesenhar = () => setVersao((v) => v + 1)
  useMapEvents({ moveend: redesenhar, zoomend: redesenhar, resize: redesenhar })

  const indice = useMemo(() => {
    const s = new Supercluster<Propriedades>({ radius: 50, maxZoom: 16 })
    s.load(ocorrencias)
    return s
  }, [ocorrencias])

  const b = mapa.getBounds()
  const itens = indice.getClusters([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()], Math.round(mapa.getZoom()))

  return (
    <>
      {itens.map((item) => {
        const [lon, lat] = item.geometry.coordinates
        if ('cluster' in item.properties && item.properties.cluster) {
          const grupo = item.properties as Supercluster.ClusterProperties
          const n = grupo.point_count
          const tamanho = n < 10 ? 34 : n < 100 ? 42 : 50
          return (
            <Marker
              key={`c${grupo.cluster_id}`}
              position={[lat, lon]}
              icon={L.divIcon({
                html: `<span>${n}</span>`,
                className: 'dbeeas-cluster',
                iconSize: [tamanho, tamanho],
              })}
              eventHandlers={{
                click: () =>
                  mapa.flyTo([lat, lon], Math.min(indice.getClusterExpansionZoom(grupo.cluster_id), 18)),
              }}
              title={`${n} ocorrências — clique para aproximar`}
            />
          )
        }
        const p = item.properties as Propriedades
        const c = cor.get(p.especie_id) ?? COR_OUTRAS
        return (
          <PontoOcorrencia key={`${p.foto_id ?? ''}${lat}${lon}${p.especie_id}${p.data}`} lat={lat} lon={lon} p={p} cor={c} />
        )
      })}
    </>
  )
}

function PontoOcorrencia({ lat, lon, p, cor }: { lat: number; lon: number; p: Propriedades; cor: string }) {
  const popup = (
    <Popup>
      <div className="min-w-44 space-y-1 text-sm">
        {p.url_miniatura && <img src={urlArquivo(p.url_miniatura)} alt="" className="mb-2 w-full rounded" />}
        <p className="font-semibold italic">{p.especie}</p>
        <p>{p.data ? dataBR(p.data) : 'Data não informada'}</p>
        {p.revisada && <p className="text-xs">✓ Revisada por uma pessoa</p>}
        {p.aproximada && (
          <p className="text-xs">Espécie sensível: localização aproximada (área de cerca de {p.raio_km} km).</p>
        )}
        {p.coleta && p.coleta_id && (
          <p>
            <Link to={`/coletas/${p.coleta_id}`} className="font-semibold underline">
              {p.coleta}
            </Link>
          </p>
        )}
        {!p.minha && !p.coleta && <p className="text-xs">Registro de outra pessoa.</p>}
      </div>
    </Popup>
  )
  if (p.aproximada && p.raio_km) {
    return (
      <Circle
        center={[lat, lon]}
        radius={(p.raio_km * 1000) / 2}
        pathOptions={{ color: cor, weight: 2, dashArray: '6 6', fillColor: cor, fillOpacity: 0.12 }}
      >
        {popup}
      </Circle>
    )
  }
  return (
    <CircleMarker
      center={[lat, lon]}
      radius={7}
      // Anel branco separa pontos sobrepostos
      pathOptions={{ color: '#ffffff', weight: 2, fillColor: cor, fillOpacity: 1 }}
    >
      {popup}
    </CircleMarker>
  )
}

export default function Mapa() {
  const [params, setParams] = useSearchParams()
  const escopo = params.get('escopo') === 'todas' ? 'todas' : 'minhas'
  const filtros = {
    escopo,
    especie_id: params.get('especie') ?? '',
    coleta_id: params.get('coleta') ?? '',
    inicio: params.get('inicio') ?? '',
    fim: params.get('fim') ?? '',
  }
  const mudar = (chave: string, valor: string) => {
    const novo = new URLSearchParams(params)
    if (valor) novo.set(chave, valor)
    else novo.delete(chave)
    if (chave === 'escopo' && valor === 'todas') novo.delete('coleta')
    setParams(novo, { replace: true })
  }

  const consulta = new URLSearchParams({ escopo })
  if (filtros.especie_id) consulta.set('especie_id', filtros.especie_id)
  if (filtros.coleta_id && escopo === 'minhas') consulta.set('coleta_id', filtros.coleta_id)
  if (filtros.inicio) consulta.set('inicio', filtros.inicio)
  if (filtros.fim) consulta.set('fim', filtros.fim)

  const dados = useQuery({
    queryKey: ['mapa', consulta.toString()],
    queryFn: () => api<GeoJSON.FeatureCollection<GeoJSON.Point, Propriedades>>(`/v1/mapa/ocorrencias?${consulta}`),
  })
  const especies = useQuery({ queryKey: ['especies'], queryFn: () => api<Especie[]>('/v1/especies') })
  const coletas = useQuery({
    queryKey: ['coletas', 'mapa'],
    queryFn: () => api<Pagina<Coleta>>('/v1/coletas?por_pagina=100'),
  })

  const ocorrencias = useMemo(() => (dados.data?.features ?? []) as Ocorrencia[], [dados.data])
  const { cor, legenda } = useMemo(() => coresPorEspecie(ocorrencias), [ocorrencias])
  const aproximadas = ocorrencias.filter((o) => o.properties.aproximada).length
  const outras = legenda.filter((e) => e.cor === COR_OUTRAS)

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-tinta-900">Mapa de ocorrências</h1>
        <p className="mt-1 text-sm text-tinta-500">Onde cada espécie foi encontrada.</p>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-tinta-100 bg-white p-4">
        <div role="group" aria-label="Quais ocorrências" className="flex rounded-lg border border-tinta-100 p-0.5">
          {[
            ['minhas', 'Minhas coletas'],
            ['todas', 'Toda a plataforma'],
          ].map(([v, n]) => (
            <button
              key={v}
              aria-pressed={escopo === v}
              onClick={() => mudar('escopo', v === 'minhas' ? '' : v)}
              className={`rounded-md px-3 py-1.5 text-sm font-semibold ${escopo === v ? 'bg-tinta-700 text-white' : 'text-tinta-800 hover:bg-tinta-50'}`}
            >
              {n}
            </button>
          ))}
        </div>
        <Selecao rotulo="Espécie" className="w-full sm:w-52" value={filtros.especie_id} onChange={(e) => mudar('especie', e.target.value)}>
          <option value="">Todas</option>
          {especies.data?.map((e) => (
            <option key={e.id} value={e.id}>{e.nome_cientifico}</option>
          ))}
        </Selecao>
        {escopo === 'minhas' && (
          <Selecao rotulo="Coleta" className="w-full sm:w-52" value={filtros.coleta_id} onChange={(e) => mudar('coleta', e.target.value)}>
            <option value="">Todas</option>
            {coletas.data?.itens.map((c) => (
              <option key={c.id} value={c.id}>{c.nome}</option>
            ))}
          </Selecao>
        )}
        <Campo rotulo="De" type="date" className="w-[47%] sm:w-40" value={filtros.inicio} onChange={(e) => mudar('inicio', e.target.value)} />
        <Campo rotulo="Até" type="date" className="w-[47%] sm:w-40" value={filtros.fim} onChange={(e) => mudar('fim', e.target.value)} />
        {(filtros.especie_id || filtros.coleta_id || filtros.inicio || filtros.fim) && (
          <button
            className="pb-3 text-sm font-semibold text-tinta-500 hover:text-tinta-800"
            onClick={() => setParams(escopo === 'todas' ? { escopo } : {}, { replace: true })}
          >
            Limpar filtros
          </button>
        )}
      </div>

      {dados.error && <Alerta>{mensagemErro(dados.error)}</Alerta>}

      <div className="grid gap-4 lg:grid-cols-[1fr_18rem]">
        <div className="relative h-[65vh] min-h-96 overflow-hidden rounded-2xl border border-tinta-100">
          <MapContainer center={CENTRO_BRASIL} zoom={4} className="h-full w-full" scrollWheelZoom>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {/* Pontos antes de AjustarZoom: assim já está ouvindo o mapa quando o zoom muda */}
            <Pontos ocorrencias={ocorrencias} cor={cor} />
            <AjustarZoom ocorrencias={ocorrencias} />
          </MapContainer>
          {dados.isFetching && (
            <div className="absolute right-3 top-3 z-[500] rounded-full bg-white px-3 py-1 text-xs font-semibold text-tinta-700 shadow">
              Carregando…
            </div>
          )}
        </div>

        <aside className="space-y-4 rounded-2xl border border-tinta-100 bg-white p-4 text-sm">
          <div>
            <p className="text-2xl font-bold text-tinta-900">{ocorrencias.length}</p>
            <p className="text-tinta-500">ocorrência(s) no mapa</p>
          </div>
          {legenda.length > 0 && (
            <ul className="space-y-2" aria-label="Legenda">
              {legenda
                .filter((e) => e.cor !== COR_OUTRAS)
                .map((e) => (
                  <li key={e.id} className="flex items-center gap-2">
                    <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: e.cor }} aria-hidden />
                    <span className="flex-1 truncate italic text-tinta-800">{e.nome}</span>
                    <span className="tabular-nums text-tinta-500">{e.n}</span>
                  </li>
                ))}
              {outras.length > 0 && (
                <li className="flex items-start gap-2">
                  <span className="mt-1 h-3 w-3 shrink-0 rounded-full" style={{ background: COR_OUTRAS }} aria-hidden />
                  <span className="flex-1 text-tinta-800">
                    Outras espécies ({outras.length})
                    <span className="block text-xs text-tinta-500">Use o filtro de espécie para vê-las em destaque.</span>
                  </span>
                  <span className="tabular-nums text-tinta-500">{outras.reduce((s, e) => s + e.n, 0)}</span>
                </li>
              )}
            </ul>
          )}
          <div className="space-y-2 border-t border-tinta-100 pt-3 text-xs text-tinta-500">
            <p className="flex items-center gap-2">
              <span className="dbeeas-cluster !static !h-6 !w-6 !text-[11px]"><span>5</span></span>
              Grupo de ocorrências próximas: clique para aproximar.
            </p>
            {aproximadas > 0 && (
              <p className="flex items-center gap-2">
                <span className="h-5 w-5 shrink-0 rounded-full border-2 border-dashed border-tinta-500" aria-hidden />
                {aproximadas} ocorrência(s) de espécie sensível com localização aproximada.
              </p>
            )}
            {escopo === 'todas' && (
              <p>Ocorrências de outras pessoas aparecem sem foto e sem o nome da coleta.</p>
            )}
            <p>Fotos sem GPS usam o ponto da coleta. Fotos sem nenhuma localização não aparecem.</p>
          </div>
        </aside>
      </div>

      {!dados.isLoading && ocorrencias.length === 0 && (
        <p className="text-center text-sm text-tinta-500">
          Nenhuma ocorrência com localização{escopo === 'minhas' ? ' nas suas coletas' : ''} para estes filtros.
        </p>
      )}
    </div>
  )
}
