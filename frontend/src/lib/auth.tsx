import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  api,
  definirToken,
  quandoSessaoEncerrar,
  renovarSessao,
  type Perfil,
  type Sessao,
  type Usuario,
} from './api'

export interface DadosCadastro {
  nome: string
  email: string
  senha: string
  perfil: Exclude<Perfil, 'admin'>
  instituicao: string
  aceite_termos: boolean
  consentimento_uso_fotos: boolean
}

interface ContextoAuth {
  usuario: Usuario | null
  carregando: boolean
  entrar: (email: string, senha: string) => Promise<void>
  cadastrar: (dados: DadosCadastro) => Promise<void>
  sair: () => Promise<void>
  aplicarSessao: (sessao: Sessao) => void
  atualizarUsuario: (usuario: Usuario | null) => void
}

const Contexto = createContext<ContextoAuth | null>(null)

export function ProvedorAuth({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [carregando, setCarregando] = useState(true)
  const consultas = useQueryClient()

  const aplicarSessao = useCallback(
    (sessao: Sessao) => {
      // Outra pessoa entrando no mesmo navegador não pode ver dados guardados da anterior
      consultas.clear()
      definirToken(sessao.access_token)
      setUsuario(sessao.usuario)
    },
    [consultas],
  )

  // Ao abrir o site, tenta recuperar a sessão pelo cookie
  useEffect(() => {
    quandoSessaoEncerrar(() => setUsuario(null))
    renovarSessao()
      .then((sessao) => sessao && aplicarSessao(sessao))
      .finally(() => setCarregando(false))
  }, [aplicarSessao])

  const valor = useMemo<ContextoAuth>(
    () => ({
      usuario,
      carregando,
      aplicarSessao,
      atualizarUsuario: setUsuario,
      entrar: async (email, senha) => {
        aplicarSessao(
          await api<Sessao>('/v1/auth/login', { method: 'POST', body: { email, senha }, semRenovar: true }),
        )
      },
      cadastrar: async (dados) => {
        aplicarSessao(await api<Sessao>('/v1/auth/cadastro', { method: 'POST', body: dados, semRenovar: true }))
      },
      sair: async () => {
        try {
          await api('/v1/auth/logout', { method: 'POST', semRenovar: true })
        } finally {
          definirToken(null)
          setUsuario(null)
          consultas.clear()
        }
      },
    }),
    [usuario, carregando, aplicarSessao, consultas],
  )

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(Contexto)
  if (!ctx) throw new Error('useAuth precisa estar dentro de <ProvedorAuth>')
  return ctx
}
