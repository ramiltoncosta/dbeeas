import { useState } from 'react'
import { Link, Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'
import { NOMES_PERFIL } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Carregando, Logo } from './ui'

export function Rodape() {
  return (
    <footer className="border-t border-tinta-100 bg-white">
      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 text-sm text-tinta-500 sm:grid-cols-[auto_1fr_auto] sm:items-center">
        <img src="/rcgj.png" alt="RCGJ Sistemas Inteligentes" width={72} height={66} className="h-16 w-auto" />
        <div className="space-y-1">
          <p className="font-semibold text-tinta-800">DBeeAS – Sistema inteligente de reconhecimento de abelhas pela asa</p>
          <p>Desenvolvido pela RCGJ Sistemas Inteligentes, CNPJ 66.904.746/0001-38.</p>
          <p>Projeto apoiado pelo Programa Centelha.</p>
        </div>
        <nav aria-label="Links do rodapé" className="flex flex-wrap gap-x-4 gap-y-2">
          <Link to="/especies" className="hover:text-tinta-800">Espécies</Link>
          <Link to="/#contato" className="hover:text-tinta-800">Contato</Link>
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

/** Páginas públicas (início, termos, privacidade).
 *  `contido`: centraliza o conteúdo com margens (usado nas páginas de espécies). */
export function LayoutPublico({ contido = false }: { contido?: boolean }) {
  const { usuario } = useAuth()
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-tinta-100 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <Link to="/" aria-label="Página inicial do DBeeAS">
            <Logo />
          </Link>
          <nav className="flex items-center gap-1 whitespace-nowrap text-sm font-semibold sm:gap-2">
            <NavLink
              to="/especies"
              className={({ isActive }) =>
                // No celular, "Espécies" fica no rodapé e na página inicial (não cabe no topo)
                `hidden rounded-lg px-3 py-2 hover:bg-tinta-50 sm:inline-block ${isActive ? 'text-tinta-900 underline underline-offset-4' : 'text-tinta-800'}`
              }
            >
              Espécies
            </NavLink>
            {usuario ? (
              <Link to="/painel" className="rounded-lg bg-tinta-700 px-4 py-2 text-white hover:bg-tinta-800">
                Ir para o painel
              </Link>
            ) : (
              <>
                <Link to="/entrar" className="rounded-lg px-2 py-2 text-tinta-800 hover:bg-tinta-50 sm:px-3">
                  Entrar
                </Link>
                <Link to="/cadastrar" className="rounded-lg bg-mel-500 px-3 py-2 text-tinta-900 hover:bg-mel-400 sm:px-4">
                  Criar conta
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="flex-1">
        {contido ? (
          <div className="mx-auto w-full max-w-6xl px-4 py-8">
            <Outlet />
          </div>
        ) : (
          <Outlet />
        )}
      </main>
      <Rodape />
    </div>
  )
}

/** Páginas abertas ao público que também fazem parte da área logada (as fichas das
 *  espécies): quem está logado vê com o menu do sistema; visitantes, com o do site. */
export function LayoutConformeSessao() {
  const { usuario, carregando } = useAuth()
  if (carregando) return <Carregando />
  return usuario ? <LayoutApp /> : <LayoutPublico contido />
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
    { para: '/mapa', texto: 'Mapa' },
    { para: '/especies', texto: 'Espécies' },
    { para: '/conta', texto: 'Minha conta' },
    ...(usuario.perfil === 'admin' ? [{ para: '/admin', texto: 'Administração' }] : []),
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
          <nav className="hidden items-center gap-1 lg:flex">
            {links.map((l) => (
              <NavLink key={l.para} to={l.para} className={estiloLink}>
                {l.texto}
              </NavLink>
            ))}
          </nav>
          <div className="hidden items-center gap-3 lg:flex">
            <div className="text-right leading-tight">
              <p className="text-sm font-semibold text-tinta-800">{usuario.nome}</p>
              <p className="text-xs text-tinta-500">{NOMES_PERFIL[usuario.perfil]}</p>
            </div>
            <button onClick={sair} className="rounded-lg px-3 py-2 text-sm text-tinta-500 hover:bg-tinta-50 hover:text-tinta-800">
              Sair
            </button>
          </div>
          <button
            className="rounded-lg p-2 text-tinta-800 hover:bg-tinta-50 lg:hidden"
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
          <nav className="space-y-1 border-t border-tinta-100 px-4 py-3 lg:hidden" onClick={() => setMenuAberto(false)}>
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

/** Rotas só para administradores, com as abas da administração */
export function SomenteAdmin() {
  const { usuario } = useAuth()
  if (usuario?.perfil !== 'admin') return <Navigate to="/painel" replace />
  const abas = [
    { para: '/admin/usuarios', texto: 'Usuários' },
    { para: '/admin/especies', texto: 'Espécies e fichas' },
    { para: '/admin/mensagens', texto: 'Mensagens' },
  ]
  return (
    <div className="space-y-6">
      <nav aria-label="Administração" className="flex gap-1 overflow-x-auto border-b border-tinta-100">
        {abas.map((a) => (
          <NavLink
            key={a.para}
            to={a.para}
            className={({ isActive }) =>
              `-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-semibold ${
                isActive ? 'border-mel-500 text-tinta-900' : 'border-transparent text-tinta-500 hover:text-tinta-800'
              }`
            }
          >
            {a.texto}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  )
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
