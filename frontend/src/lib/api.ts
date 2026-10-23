/**
 * Cliente da API do DBeeAS.
 *
 * - O token de acesso fica só na memória (some ao fechar a aba).
 * - A sessão é mantida por um cookie protegido que o navegador envia
 *   automaticamente para /v1/auth/refresh.
 * - Quando o token de acesso expira, renovamos a sessão uma vez e repetimos o pedido.
 */

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export type Perfil = 'pesquisador' | 'orgao_publico' | 'estudante' | 'admin'

export const NOMES_PERFIL: Record<Perfil, string> = {
  pesquisador: 'Pesquisador(a)',
  orgao_publico: 'Órgão público',
  estudante: 'Estudante',
  admin: 'Administrador(a)',
}

export interface Usuario {
  id: string
  nome: string
  email: string
  perfil: Perfil
  instituicao: string | null
  ativo: boolean
  perfil_aprovado: boolean
  consentimento_uso_fotos: boolean
  criado_em: string
}

export interface UsuarioAdmin extends Usuario {
  ultimo_login_em: string | null
  termos_aceitos_em: string
  plano: {
    status: string
    plano: string | null
    fim: string | null
    usadas: number
    limite: number | null
    pedido: string | null
  } | null
}

export interface Sessao {
  access_token: string
  expires_in: number
  usuario: Usuario
}

export class ErroApi extends Error {
  status: number
  constructor(status: number, mensagem: string) {
    super(mensagem)
    this.status = status
  }
}

let tokenAcesso: string | null = null
let renovando: Promise<Sessao | null> | null = null
let aoEncerrarSessao: (() => void) | null = null

export function obterToken() {
  return tokenAcesso
}

/** Endereço completo de um arquivo (os links das imagens vêm da API como "/v1/arquivos/..."). */
export function urlArquivo(caminho: string | null | undefined) {
  return caminho ? `${API_URL}${caminho}` : undefined
}

/** Mensagem de erro amigável a partir de qualquer erro. */
export function mensagemErro(e: unknown) {
  return e instanceof ErroApi ? e.message : 'Algo deu errado. Tente novamente.'
}

export function definirToken(token: string | null) {
  tokenAcesso = token
}

export function quandoSessaoEncerrar(fn: () => void) {
  aoEncerrarSessao = fn
}

async function lerErro(r: Response): Promise<string> {
  try {
    const corpo = await r.json()
    if (typeof corpo.detail === 'string') return corpo.detail
    // Erros de validação do FastAPI vêm como lista
    if (Array.isArray(corpo.detail)) return 'Verifique os dados informados.'
    if (typeof corpo.error === 'string') return corpo.error
  } catch {
    /* resposta sem JSON */
  }
  if (r.status === 429) return 'Muitas tentativas. Aguarde um minuto e tente de novo.'
  return 'Não foi possível concluir. Tente novamente.'
}

/** Tenta renovar a sessão usando o cookie. Vários pedidos simultâneos compartilham a mesma renovação. */
export function renovarSessao(): Promise<Sessao | null> {
  if (!renovando) {
    renovando = fetch(`${API_URL}/v1/auth/refresh`, { method: 'POST', credentials: 'include' })
      .then(async (r) => {
        if (!r.ok) return null
        const sessao = (await r.json()) as Sessao
        tokenAcesso = sessao.access_token
        return sessao
      })
      .catch(() => null)
      .finally(() => {
        renovando = null
      })
  }
  return renovando
}

interface Opcoes {
  method?: string
  body?: unknown
  semRenovar?: boolean
}

export async function api<T>(caminho: string, opcoes: Opcoes = {}): Promise<T> {
  const fazer = () =>
    fetch(`${API_URL}${caminho}`, {
      method: opcoes.method ?? 'GET',
      credentials: 'include',
      headers: {
        ...(opcoes.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(tokenAcesso ? { Authorization: `Bearer ${tokenAcesso}` } : {}),
      },
      body: opcoes.body !== undefined ? JSON.stringify(opcoes.body) : undefined,
    })

  let r: Response
  try {
    r = await fazer()
  } catch {
    throw new ErroApi(0, 'Sem conexão com o servidor. Verifique sua internet.')
  }

  if (r.status === 401 && tokenAcesso && !opcoes.semRenovar) {
    const sessao = await renovarSessao()
    if (sessao) {
      r = await fazer()
    } else {
      tokenAcesso = null
      aoEncerrarSessao?.()
    }
  }

  if (!r.ok) throw new ErroApi(r.status, await lerErro(r))
  if (r.status === 204) return undefined as T
  return (await r.json()) as T
}

/** Baixa um arquivo da API (com o token) e salva no computador. */
export async function baixarArquivo(caminho: string, nomeArquivo: string) {
  const r = await fetch(`${API_URL}${caminho}`, {
    credentials: 'include',
    headers: tokenAcesso ? { Authorization: `Bearer ${tokenAcesso}` } : {},
  })
  if (!r.ok) throw new ErroApi(r.status, await lerErro(r))
  const url = URL.createObjectURL(await r.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = nomeArquivo
  link.click()
  URL.revokeObjectURL(url)
}

/** Envia um arquivo (multipart) para a API e devolve a resposta em JSON. */
export async function enviarArquivo<T>(caminho: string, campo: string, arquivo: File): Promise<T> {
  const fazer = () => {
    const corpo = new FormData()
    corpo.append(campo, arquivo)
    return fetch(`${API_URL}${caminho}`, {
      method: 'POST',
      credentials: 'include',
      headers: tokenAcesso ? { Authorization: `Bearer ${tokenAcesso}` } : {},
      body: corpo,
    })
  }
  let r: Response
  try {
    r = await fazer()
  } catch {
    throw new ErroApi(0, 'Sem conexão com o servidor. Verifique sua internet.')
  }
  if (r.status === 401 && tokenAcesso && (await renovarSessao())) r = await fazer()
  if (!r.ok) throw new ErroApi(r.status, await lerErro(r))
  return (await r.json()) as T
}
