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
import L from 'leaflet'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Circle, CircleMarker, MapContainer, Marker, Popup, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import { Link } from 'react-router-dom'
import Supercluster from 'supercluster'
import { urlArquivo } from '../lib/api'
import { dataBR } from '../lib/coletas'
import { CENTRO_BRASIL, COR_OUTRAS, type Ocorrencia, type Propriedades } from '../lib/mapa'

type AoAbrirFoto = ((fotoId: string) => void) | undefined

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

function Pontos({
  ocorrencias,
  cor,
  aoAbrirFoto,
}: {
  ocorrencias: Ocorrencia[]
  cor: Map<number, string>
  aoAbrirFoto: AoAbrirFoto
}) {
  const mapa = useMap()
  // Redesenha quando o mapa muda; o zoom e a área visível são lidos direto do mapa.
  // Com um balão aberto, o mapa se desloca sozinho para mostrá-lo inteiro: nesse caso não
  // redesenhamos, senão o balão fecharia logo depois de abrir.
  const [, setVersao] = useState(0)
  const redesenhar = () => setVersao((v) => v + 1)
  const balaoAberto = useRef(false)
  useMapEvents({
    zoomend: redesenhar,
    resize: redesenhar,
    moveend: () => !balaoAberto.current && redesenhar(),
    popupopen: () => {
      balaoAberto.current = true
    },
    popupclose: () => {
      balaoAberto.current = false
      redesenhar()
    },
  })

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
          <PontoOcorrencia
            key={`${p.foto_id ?? ''}${lat}${lon}${p.especie_id}${p.data}`}
            lat={lat}
            lon={lon}
            p={p}
            cor={c}
            aoAbrirFoto={aoAbrirFoto}
          />
        )
      })}
    </>
  )
}

function PontoOcorrencia({
  lat,
  lon,
  p,
  cor,
  aoAbrirFoto,
}: {
  lat: number
  lon: number
  p: Propriedades
  cor: string
  aoAbrirFoto: AoAbrirFoto
}) {
  // Ao passar o mouse: prévia grande da foto, espécie e data (some ao tirar o mouse)
  const previa = (
    <Tooltip
      direction="top"
      offset={[0, -10]}
      opacity={1}
      className="dbeeas-previa"
    >
      <div className="w-56 space-y-1 text-sm">
        {p.url_miniatura && (
          <img src={urlArquivo(p.url_miniatura)} alt="" className="h-36 w-full rounded object-cover" />
        )}
        <p className="font-semibold italic text-tinta-900">{p.especie}</p>
        <p className="text-tinta-500">
          {p.data ? dataBR(p.data) : 'Data não informada'}
          {p.revisada && ' · ✓ revisada'}
        </p>
        {p.aproximada && <p className="text-xs text-tinta-500">Localização aproximada (cerca de {p.raio_km} km)</p>}
        {p.foto_id && (
          <p className="text-xs font-semibold text-tinta-700">
            {aoAbrirFoto ? 'Clique para abrir a foto' : 'Clique para mais opções'}
          </p>
        )}
      </div>
    </Tooltip>
  )

  // Ao clicar: fica aberto até fechar, com os links
  const popup = (
    <Popup autoPanPadding={[24, 24]}>
      <div className="w-60 space-y-1 text-sm">
        {p.url_miniatura && (
          <img src={urlArquivo(p.url_miniatura)} alt="" className="mb-2 h-40 w-full rounded object-cover" />
        )}
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
  // Na página da coleta, clicar no ponto abre a foto grande (com a caixa do modelo e a revisão)
  const abreFoto = aoAbrirFoto && p.foto_id
  const eventos: L.LeafletEventHandlerFnMap = {
    // Ponto na metade de cima do mapa: a prévia abre para baixo, para não ser cortada
    tooltipopen: (e) => {
      const dica = (e as L.TooltipEvent).tooltip
      const camada = e.target as L.CircleMarker
      const mapa = (camada as unknown as { _map?: L.Map })._map
      if (!mapa) return
      const emCima = mapa.latLngToContainerPoint(camada.getLatLng()).y < mapa.getSize().y / 2
      const direcao = emCima ? 'bottom' : 'top'
      if (dica.options.direction !== direcao) {
        dica.options.direction = direcao
        dica.options.offset = L.point(0, emCima ? 10 : -10)
        dica.update() // reposiciona já com a nova direção
      }
    },
    ...(abreFoto ? { click: () => aoAbrirFoto(p.foto_id!) } : {}),
  }
  const balao = abreFoto ? null : popup

  if (p.aproximada && p.raio_km) {
    return (
      <Circle
        center={[lat, lon]}
        radius={(p.raio_km * 1000) / 2}
        pathOptions={{ color: cor, weight: 2, dashArray: '6 6', fillColor: cor, fillOpacity: 0.12 }}
        eventHandlers={eventos}
      >
        {previa}
        {balao}
      </Circle>
    )
  }
  return (
    <CircleMarker
      center={[lat, lon]}
      radius={7}
      // Anel branco separa pontos sobrepostos
      pathOptions={{ color: '#ffffff', weight: 2, fillColor: cor, fillOpacity: 1 }}
      eventHandlers={eventos}
    >
      {previa}
      {balao}
    </CircleMarker>
  )
}

interface Props {
  ocorrencias: Ocorrencia[]
  cor: Map<number, string>
  /** Se informado, clicar num ponto (das suas fotos) abre a foto em vez do balão */
  aoAbrirFoto?: (fotoId: string) => void
  className?: string
}

export default function MapaOcorrencias({ ocorrencias, cor, aoAbrirFoto, className = '' }: Props) {
  return (
    <MapContainer center={CENTRO_BRASIL} zoom={4} className={className} scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {/* Pontos antes de AjustarZoom: assim já está ouvindo o mapa quando o zoom muda */}
      <Pontos ocorrencias={ocorrencias} cor={cor} aoAbrirFoto={aoAbrirFoto} />
      <AjustarZoom ocorrencias={ocorrencias} />
    </MapContainer>
  )
}
