import { useState } from 'react'
import { Link, Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'
import { NOMES_PERFIL } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Carregando, Logo } from './ui'

export function Rodape() {
  return (
    <footer className="border-t border-tinta-100 bg-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-6 text-sm text-tinta-500 sm:flex-row sm:items-center sm:justify-between">
        <p>
          DBeeAS · RCGJ Sistemas Inteligentes · Projeto apoiado pelo Programa Centelha
        </p>
        <nav className="flex gap-4">
          <Link to="/termos" className="hover:text-tinta-800">Termos de uso</Link>
          <Link to="/privacidade" className="hover:text-tinta-800">Privacidade</Link>
        </nav>
      </div>
    </footer>
  )
}

/** Telas de entrar, cadastrar e recuperar senha */
export function LayoutConta() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="px-4 py-5">
        <div className="mx-auto max-w-6xl">
          <Link to="/" aria-label="Página inicial do DBeeAS">
            <Logo />
          </Link>
        </div>
      </header>
      <main className="flex flex-1 items-start justify-center px-4 pb-12 pt-4 sm:pt-10">
        <div className="w-full max-w-md">
          <Outlet />
        </div>
      </main>
      <Rodape />
    </div>
  )
}

/** Páginas públicas (início, termos, privacidade) */
export function LayoutPublico() {
  const { usuario } = useAuth()
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-tinta-100 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <Link to="/" aria-label="Página inicial do DBeeAS">
            <Logo />
          </Link>
          <nav className="flex items-center gap-2 text-sm font-semibold">
            {usuario ? (
              <Link to="/painel" className="rounded-lg bg-tinta-700 px-4 py-2 text-white hover:bg-tinta-800">
                Ir para o painel
              </Link>
            ) : (
              <>
                <Link to="/entrar" className="rounded-lg px-3 py-2 text-tinta-800 hover:bg-tinta-50">
                  Entrar
                </Link>
                <Link to="/cadastrar" className="rounded-lg bg-mel-500 px-4 py-2 text-tinta-900 hover:bg-mel-400">
                  Criar conta
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <Rodape />
    </div>
  )
}

/** Área logada. Quem não estiver logado vai para a tela de entrar. */
export function LayoutApp() {
  const { usuario, carregando, sair } = useAuth()
  const local = useLocation()
  const [menuAberto, setMenuAberto] = useState(false)

  if (carregando) return <Carregando />
  if (!usuario) return <Navigate to="/entrar" replace state={{ de: local.pathname }} />

  const links = [
    { para: '/painel', texto: 'Painel' },
    { para: '/coletas', texto: 'Coletas' },
    { para: '/identificar', texto: 'Identificar' },
    { para: '/conta', texto: 'Minha conta' },
    ...(usuario.perfil === 'admin' ? [{ para: '/admin/usuarios', texto: 'Usuários' }] : []),
  ]

  const estiloLink = ({ isActive }: { isActive: boolean }) =>
    `block rounded-lg px-3 py-2 text-sm font-semibold ${
      isActive ? 'bg-tinta-700 text-white' : 'text-tinta-800 hover:bg-tinta-50'
    }`

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-tinta-100 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/painel" aria-label="Painel">
            <Logo />
          </Link>
          <nav className="hidden items-center gap-1 md:flex">
            {links.map((l) => (
              <NavLink key={l.para} to={l.para} className={estiloLink}>
                {l.texto}
              </NavLink>
            ))}
          </nav>
          <div className="hidden items-center gap-3 md:flex">
            <div className="text-right leading-tight">
              <p className="text-sm font-semibold text-tinta-800">{usuario.nome}</p>
              <p className="text-xs text-tinta-500">{NOMES_PERFIL[usuario.perfil]}</p>
            </div>
            <button onClick={sair} className="rounded-lg px-3 py-2 text-sm text-tinta-500 hover:bg-tinta-50 hover:text-tinta-800">
              Sair
            </button>
          </div>
          <button
            className="rounded-lg p-2 text-tinta-800 hover:bg-tinta-50 md:hidden"
            onClick={() => setMenuAberto((v) => !v)}
            aria-expanded={menuAberto}
            aria-label="Abrir menu"
          >
            <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        {menuAberto && (
          <nav className="space-y-1 border-t border-tinta-100 px-4 py-3 md:hidden" onClick={() => setMenuAberto(false)}>
            <p className="px-3 pb-2 text-sm text-tinta-500">
              {usuario.nome} · {NOMES_PERFIL[usuario.perfil]}
            </p>
            {links.map((l) => (
              <NavLink key={l.para} to={l.para} className={estiloLink}>
                {l.texto}
              </NavLink>
            ))}
            <button onClick={sair} className="block w-full rounded-lg px-3 py-2 text-left text-sm font-semibold text-tinta-500 hover:bg-tinta-50">
              Sair
            </button>
          </nav>
        )}
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>
      <Rodape />
    </div>
  )
}

/** Rotas só para administradores */
export function SomenteAdmin() {
  const { usuario } = useAuth()
  if (usuario?.perfil !== 'admin') return <Navigate to="/painel" replace />
  return <Outlet />
}

/** Telas de entrar/cadastrar: quem já está logado vai direto para o painel */
export function SomenteVisitante() {
  const { usuario, carregando } = useAuth()
  const local = useLocation()
  if (carregando) return <Carregando />
  if (usuario) {
    const destino = (local.state as { de?: string } | null)?.de ?? '/painel'
    return <Navigate to={destino} replace />
  }
  return <Outlet />
}
