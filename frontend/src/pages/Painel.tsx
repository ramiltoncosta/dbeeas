import { Link } from 'react-router-dom'
import { Alerta, Cartao } from '../components/ui'
import { useAuth } from '../lib/auth'

export default function Painel() {
  const { usuario } = useAuth()
  if (!usuario) return null
  const primeiroNome = usuario.nome.split(' ')[0]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-tinta-900">Olá, {primeiroNome}!</h1>
        <p className="mt-1 text-tinta-500">Este é o seu painel no DBeeAS.</p>
      </div>

      {usuario.perfil === 'pesquisador' && !usuario.perfil_aprovado && (
        <Alerta tipo="info">
          Seu perfil de pesquisador está aguardando aprovação. Enquanto isso, você já pode usar o sistema
          normalmente; só a localização exata de espécies sensíveis fica oculta.
        </Alerta>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <Link to="/coletas" className="rounded-2xl border border-tinta-100 bg-white p-6 shadow-sm transition hover:border-mel-400">
          <h2 className="text-lg font-bold text-tinta-800">Coletas</h2>
          <p className="mt-1 text-sm text-tinta-500">Organize as fotos de cada saída de campo e identifique várias de uma vez.</p>
        </Link>
        <Link to="/identificar" className="rounded-2xl border border-tinta-100 bg-white p-6 shadow-sm transition hover:border-mel-400">
          <h2 className="text-lg font-bold text-tinta-800">Identificação rápida</h2>
          <p className="mt-1 text-sm text-tinta-500">Envie uma foto da asa e veja a espécie na hora.</p>
        </Link>
        <Cartao className="border-dashed">
          <p className="text-xs font-semibold uppercase tracking-wide text-mel-700">Em breve</p>
          <h2 className="mt-1 text-lg font-bold text-tinta-800">Mapa</h2>
          <p className="mt-1 text-sm text-tinta-500">Veja onde cada espécie foi encontrada.</p>
        </Cartao>
      </div>

      <p className="text-sm text-tinta-500">
        Quer revisar seus dados ou consentimentos?{' '}
        <Link to="/conta" className="font-semibold text-tinta-700 underline">Acesse Minha conta</Link>.
      </p>
    </div>
  )
}
