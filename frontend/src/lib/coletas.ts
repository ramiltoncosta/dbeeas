/** Tipos e funções de coletas e fotos. */
import { API_URL, ErroApi, obterToken, renovarSessao } from './api'

export interface Ponto {
  latitude: number
  longitude: number
}

export type Bioma = 'amazonia' | 'caatinga' | 'cerrado' | 'mata_atlantica' | 'pampa' | 'pantanal'

export const BIOMAS: Record<Bioma, string> = {
  amazonia: 'Amazônia',
  caatinga: 'Caatinga',
  cerrado: 'Cerrado',
  mata_atlantica: 'Mata Atlântica',
  pampa: 'Pampa',
  pantanal: 'Pantanal',
}

export const UFS = [
  'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA',
  'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
]

export interface Contagem {
  total: number
  na_fila: number
  processando: number
  concluidas: number
  erro: number
  identificadas: number
  nao_identificadas: number
}

export interface CamposColeta {
  nome: string
  descricao: string | null
  data_coleta: string | null
  municipio: string | null
  uf: string | null
  coletor: string | null
  tipo_armadilha: string | null
  isca_atrativa: string | null
  bioma: Bioma | null
  observacoes: string | null
  local: Ponto | null
}

export interface Coleta extends CamposColeta {
  id: string
  usuario_id: string
  criado_em: string
  atualizado_em: string
  fotos: Contagem
}

export interface Deteccao {
  especie: string
  confianca: number
  caixa: { x1: number; y1: number; x2: number; y2: number }
}

export type StatusFoto = 'na_fila' | 'processando' | 'concluida' | 'erro'
export type Sexo = 'femea' | 'macho' | 'indeterminado'

export const SEXOS: Record<Sexo, string> = { femea: 'Fêmea', macho: 'Macho', indeterminado: 'Indeterminado' }

export interface Foto {
  id: string
  coleta_id: string
  nome_original: string
  largura: number
  altura: number
  tamanho_bytes: number
  data_captura: string | null
  local: Ponto | null
  origem_local: 'exif' | 'manual' | null
  sexo: Sexo | null
  status: StatusFoto
  erro: string | null
  tentativas: number
  enviada_em: string
  processada_em: string | null
  url_miniatura: string | null
  url_media: string | null
  url_original: string | null
  identificacao: {
    identificada: boolean
    especie: string | null
    confianca: number | null
    deteccoes: Deteccao[]
    versao_modelo: string | null
    criado_em: string
  } | null
}

export interface Pagina<T> {
  itens: T[]
  total: number
  pagina: number
  por_pagina: number
}

export interface Rejeitada {
  arquivo: string
  motivo: string
}

export interface ResultadoEnvio {
  aceitas: Foto[]
  rejeitadas: Rejeitada[]
}

export const pct = (v: number | null | undefined) => (v == null ? '—' : `${Math.round(v * 100)}%`)

export const dataBR = (iso: string | null | undefined) =>
  iso ? new Date(iso.length === 10 ? `${iso}T12:00:00` : iso).toLocaleDateString('pt-BR') : '—'

/**
 * Envia uma foto com barra de progresso.
 * Usa XMLHttpRequest porque o fetch ainda não informa o progresso do envio.
 */
export function enviarFoto(
  coletaId: string,
  arquivo: File,
  aoProgredir: (fracao: number) => void,
): Promise<ResultadoEnvio> {
  const tentar = (token: string | null) =>
    new Promise<{ status: number; corpo: unknown }>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', `${API_URL}/v1/coletas/${coletaId}/fotos`)
      xhr.withCredentials = true
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      xhr.upload.onprogress = (e) => e.lengthComputable && aoProgredir(e.loaded / e.total)
      xhr.onload = () => {
        let corpo: unknown = null
        try {
          corpo = JSON.parse(xhr.responseText)
        } catch {
          /* sem JSON */
        }
        resolve({ status: xhr.status, corpo })
      }
      xhr.onerror = () => reject(new ErroApi(0, 'Falha de conexão durante o envio.'))
      const form = new FormData()
      form.append('arquivos', arquivo)
      xhr.send(form)
    })

  return (async () => {
    let r = await tentar(obterToken())
    if (r.status === 401) {
      const sessao = await renovarSessao()
      if (sessao) r = await tentar(sessao.access_token)
    }
    if (r.status < 200 || r.status >= 300) {
      const detalhe = (r.corpo as { detail?: unknown } | null)?.detail
      throw new ErroApi(r.status, typeof detalhe === 'string' ? detalhe : 'Não foi possível enviar a foto.')
    }
    return r.corpo as ResultadoEnvio
  })()
}
