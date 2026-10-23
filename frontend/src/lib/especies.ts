/** Tipos das fichas e do catálogo público de espécies. */

export interface Ficha {
  nome_popular: string | null
  autoria: string | null
  descricao: string | null
  caracteristicas: string | null
  distribuicao: string | null
  fontes: string | null
  url_imagem: string | null
  credito_imagem: string | null
  publicada: boolean
  atualizado_em: string | null
  atualizado_por?: string | null
}

export interface EspecieResumo {
  id: number
  nome_cientifico: string
  nome_popular: string | null
  autoria: string | null
  resumo: string | null
  url_imagem: string | null
  reconhecida_pelo_modelo: boolean
  ficha_publicada: boolean
  ocorrencias: number
}

export interface EspecieDetalhe extends EspecieResumo {
  sensivel: boolean
  ficha: Ficha | null
  estatisticas: {
    ocorrencias: number
    coletas: number
    estados: { uf: string; nome: string; ocorrencias: number }[]
    primeiro_ano: number | null
    ultimo_ano: number | null
  }
}
