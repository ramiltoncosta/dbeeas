/**
 * Aviso curto do saldo do plano, mostrado onde se enviam fotos.
 * Bloqueado: explica o motivo e leva a "Meu plano". Liberado: mostra quantas fotos restam.
 */
import { Link } from 'react-router-dom'
import { useMeuPlano } from '../lib/planos'

export default function SaldoPlano({ className = '' }: { className?: string }) {
  const { data } = useMeuPlano()
  if (!data || data.status === 'ilimitado') return null

  if (!data.pode_enviar) {
    return (
      <div role="alert" className={`rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 ${className}`}>
        {data.motivo_bloqueio}{' '}
        <Link to="/plano" className="font-semibold underline">Ver meu plano</Link>
      </div>
    )
  }
  const { restantes, limite } = data.uso
  if (restantes == null || limite == null) return null
  const pouco = restantes <= Math.max(5, limite * 0.1)
  return (
    <p className={`text-sm ${pouco ? 'font-semibold text-mel-700' : 'text-tinta-500'} ${className}`}>
      Restam {restantes.toLocaleString('pt-BR')} de {limite.toLocaleString('pt-BR')} fotos do seu plano neste mês.{' '}
      <Link to="/plano" className="underline">Meu plano</Link>
    </p>
  )
}
