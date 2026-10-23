/**
 * Mapa de ocorrências: onde cada espécie foi encontrada.
 *
 * - Pontos próximos são agrupados (número no círculo) e se separam ao aproximar o zoom.
 *   Fotos no mesmo lugar (ex.: sem GPS, usando o ponto da coleta) abrem em leque ao clicar.
 * - Cores: até 3 espécies ganham cor própria; as demais ficam em cinza ("outras espécies").
 *   Com mais de 3 cores no mapa, fica difícil distinguir os pontos, principalmente para
 *   quem tem daltonismo. Para ver uma espécie específica, use o filtro.
 * - Espécies sensíveis aparecem com localização aproximada (círculo tracejado) para quem
 *   não tem permissão de ver o ponto exato.
 */
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import {
  Circle,
  CircleMarker,
  MapContainer,
  Marker,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from 'react-leaflet'
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

type Contagens = Record<string, number>
interface PropsGrupo {
  especies: Contagens
}

const ZOOM_MAXIMO = 19
// Distância (em graus) abaixo da qual consideramos que as fotos estão no mesmo lugar
const MESMO_LUGAR = 0.00005

/**
 * Posições "em leque" ao redor de um ponto, em pixels: usado quando várias fotos estão no
 * mesmo lugar (ex.: fotos sem GPS, que usam o ponto da coleta). Sem isso, os pontos ficariam
 * empilhados e só o de cima apareceria.
 */
function posicoesEmLeque(n: number): [number, number][] {
  if (n <= 8) {
    const raio = 28 + n * 3
    return Array.from({ length: n }, (_, i) => {
      const angulo = (2 * Math.PI * i) / n - Math.PI / 2
      return [raio * Math.cos(angulo), raio * Math.sin(angulo)]
    })
  }
  // Muitos pontos: espiral
  let angulo = 0
  let raio = 18
  return Array.from({ length: n }, () => {
    angulo += 18 / raio + 0.35
    raio += 22 / (2 * Math.PI)
    return [raio * Math.cos(angulo), raio * Math.sin(angulo)]
  })
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
  // Grupo de fotos no mesmo lugar que está aberto em leque
  const [leque, setLeque] = useState<number | null>(null)
  useMapEvents({
    zoomstart: () => setLeque(null),
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
    click: () => setLeque(null),
  })

  const indice = useMemo(() => {
    // maxZoom acima do zoom máximo do mapa: fotos no mesmo lugar continuam agrupadas
    // (com o número) em qualquer zoom, e se abrem em leque ao clicar.
    const s = new Supercluster<Propriedades, PropsGrupo>({
      radius: 50,
      maxZoom: ZOOM_MAXIMO + 2,
      map: (p) => ({ especies: { [p.especie_id]: 1 } }),
      reduce: (acc, p) => {
        for (const [k, v] of Object.entries(p.especies)) acc.especies[k] = (acc.especies[k] ?? 0) + v
      },
    })
    s.load(ocorrencias)
    return s
  }, [ocorrencias])

  // Nome de cada espécie, para a lista ao passar o mouse sobre um grupo
  const nomes = useMemo(() => {
    const m = new Map<string, string>()
    for (const o of ocorrencias) m.set(String(o.properties.especie_id), o.properties.especie)
    return m
  }, [ocorrencias])

  function clicarGrupo(id: number, lat: number, lon: number) {
    const folhas = indice.getLeaves(id, Infinity)
    const [lon0, lat0] = folhas[0].geometry.coordinates
    const mesmoLugar = folhas.every(
      (f) =>
        Math.abs(f.geometry.coordinates[0] - lon0) < MESMO_LUGAR &&
        Math.abs(f.geometry.coordinates[1] - lat0) < MESMO_LUGAR,
    )
    const zoom = indice.getClusterExpansionZoom(id)
    if (mesmoLugar || zoom > ZOOM_MAXIMO) setLeque(leque === id ? null : id)
    else mapa.flyTo([lat, lon], zoom)
  }

  const b = mapa.getBounds()
  const itens = indice.getClusters([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()], Math.round(mapa.getZoom()))

  const ponto = (p: Propriedades, lat: number, lon: number, chave: string) => (
    <PontoOcorrencia
      key={chave}
      lat={lat}
      lon={lon}
      p={p}
      cor={cor.get(p.especie_id) ?? COR_OUTRAS}
      aoAbrirFoto={aoAbrirFoto}
    />
  )

  return (
    <>
      {itens.map((item, i) => {
        const [lon, lat] = item.geometry.coordinates
        if ('cluster' in item.properties && item.properties.cluster) {
          const grupo = item.properties as Supercluster.ClusterProperties & PropsGrupo
          const n = grupo.point_count
          const tamanho = n < 10 ? 34 : n < 100 ? 42 : 50
          const aberto = leque === grupo.cluster_id
          const contagens = Object.entries(grupo.especies).sort((x, y) => y[1] - x[1])

          // Leque aberto: cada foto ganha seu ponto, ligado ao centro por uma linha
          const folhas = aberto ? indice.getLeaves(grupo.cluster_id, Infinity) : []
          const centro = mapa.latLngToContainerPoint([lat, lon])
          const posicoes = posicoesEmLeque(folhas.length)

          return (
            <Fragment key={`c${grupo.cluster_id}`}>
              {folhas.map((f, j) => {
                const destino = mapa.containerPointToLatLng(centro.add(posicoes[j]))
                return (
                  <Fragment key={`f${j}`}>
                    <Polyline
                      positions={[[lat, lon], destino]}
                      pathOptions={{ color: '#3c6f82', weight: 1.5, opacity: 0.7, interactive: false }}
                    />
                    {ponto(f.properties, destino.lat, destino.lng, `l${grupo.cluster_id}-${j}`)}
                  </Fragment>
                )
              })}
              <Marker
                position={[lat, lon]}
                icon={L.divIcon({
                  html: `<span>${aberto ? '×' : n}</span>`,
                  className: 'dbeeas-cluster',
                  iconSize: [tamanho, tamanho],
                })}
                eventHandlers={{ click: () => clicarGrupo(grupo.cluster_id, lat, lon) }}
              >
                {!aberto && (
                  <Tooltip direction="top" offset={[0, -tamanho / 2]} opacity={1} className="dbeeas-previa">
                    <div className="w-56 space-y-1 text-sm">
                      <p className="font-semibold text-tinta-900">{n} ocorrências aqui</p>
                      <ul className="space-y-0.5">
                        {contagens.slice(0, 6).map(([id, q]) => (
                          <li key={id} className="flex items-center gap-1.5">
                            <span
                              className="h-2.5 w-2.5 shrink-0 rounded-full"
                              style={{ background: cor.get(Number(id)) ?? COR_OUTRAS }}
                            />
                            <span className="flex-1 truncate italic">{nomes.get(id)}</span>
                            <span className="text-tinta-500">{q}</span>
                          </li>
                        ))}
                        {contagens.length > 6 && <li className="text-tinta-500">e mais {contagens.length - 6} espécie(s)</li>}
                      </ul>
                      <p className="text-xs font-semibold text-tinta-700">Clique para ver cada uma</p>
                    </div>
                  </Tooltip>
                )}
              </Marker>
            </Fragment>
          )
        }
        const p = item.properties as Propriedades
        return ponto(p, lat, lon, `${p.foto_id ?? i}${lat}${lon}`)
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
          <img src={urlArquivo(p.url_miniatura)} alt="" className="h-28 w-full rounded object-cover" />
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
        bubblingMouseEvents={false}
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
      bubblingMouseEvents={false} // o clique no ponto não fecha o leque
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
    <MapContainer center={CENTRO_BRASIL} zoom={4} maxZoom={ZOOM_MAXIMO} className={className} scrollWheelZoom>
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
