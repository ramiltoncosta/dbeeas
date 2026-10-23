/** Tipos e cores do mapa de ocorrências. */

export interface Propriedades {
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

export type Ocorrencia = GeoJSON.Feature<GeoJSON.Point, Propriedades>

// Paleta categórica validada (3 primeiras cores: distinguíveis entre si também com daltonismo)
export const CORES = ['#2a78d6', '#eb6834', '#1baf7a']
export const COR_OUTRAS = '#8a8f98'
export const CENTRO_BRASIL: [number, number] = [-14.2, -51.9]

export function coresPorEspecie(ocorrencias: Ocorrencia[]) {
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
