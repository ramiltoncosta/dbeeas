/** Mapa para marcar um ponto (clique no mapa ou use a localização do aparelho). */
import 'leaflet/dist/leaflet.css'
import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import type { Ponto } from '../lib/coletas'
import { Botao } from './ui'

const CENTRO_BRASIL: [number, number] = [-14.2, -51.9]

function Cliques({ aoMarcar }: { aoMarcar: (p: Ponto) => void }) {
  useMapEvents({
    click: (e) => aoMarcar({ latitude: +e.latlng.lat.toFixed(6), longitude: +e.latlng.lng.toFixed(6) }),
  })
  return null
}

function Centralizar({ ponto }: { ponto: Ponto | null }) {
  const mapa = useMap()
  useEffect(() => {
    if (ponto) mapa.setView([ponto.latitude, ponto.longitude], Math.max(mapa.getZoom(), 12))
  }, [ponto, mapa])
  return null
}

interface Props {
  valor: Ponto | null
  aoMudar: (p: Ponto | null) => void
  altura?: string
}

export default function SeletorLocal({ valor, aoMudar, altura = 'h-72' }: Props) {
  const [localizando, setLocalizando] = useState(false)
  const [erro, setErro] = useState('')

  function minhaLocalizacao() {
    if (!navigator.geolocation) return setErro('Este navegador não informa a localização.')
    setErro('')
    setLocalizando(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        aoMudar({ latitude: +pos.coords.latitude.toFixed(6), longitude: +pos.coords.longitude.toFixed(6) })
        setLocalizando(false)
      },
      () => {
        setErro('Não foi possível obter sua localização. Clique no mapa para marcar.')
        setLocalizando(false)
      },
      { enableHighAccuracy: true, timeout: 15000 },
    )
  }

  return (
    <div className="space-y-2">
      <div className={`overflow-hidden rounded-lg border border-tinta-100 ${altura}`}>
        <MapContainer
          center={valor ? [valor.latitude, valor.longitude] : CENTRO_BRASIL}
          zoom={valor ? 12 : 4}
          className="h-full w-full"
          scrollWheelZoom
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <Cliques aoMarcar={aoMudar} />
          <Centralizar ponto={valor} />
          {valor && (
            <CircleMarker
              center={[valor.latitude, valor.longitude]}
              radius={9}
              pathOptions={{ color: '#1f4e5f', weight: 3, fillColor: '#e0a23a', fillOpacity: 0.9 }}
            />
          )}
        </MapContainer>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Botao type="button" variante="secundario" className="!py-1.5" carregando={localizando} onClick={minhaLocalizacao}>
          Usar minha localização
        </Botao>
        {valor && (
          <>
            <span className="font-mono text-xs text-tinta-500">
              {valor.latitude.toFixed(5)}, {valor.longitude.toFixed(5)}
            </span>
            <button type="button" className="text-xs font-semibold text-red-700 hover:underline" onClick={() => aoMudar(null)}>
              Remover ponto
            </button>
          </>
        )}
        {!valor && <span className="text-xs text-tinta-500">Clique no mapa para marcar o ponto.</span>}
      </div>
      {erro && <p className="text-xs text-red-700">{erro}</p>}
    </div>
  )
}
