import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { useId } from 'react'

export function Logo({ claro = false }: { claro?: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden="true">
        <path d="M16 2 28 9v14l-12 7-12-7V9z" fill="#E0A23A" />
        <path
          d="M16 9c-4 3-6 7-6 11m6-11c4 3 6 7 6 11M16 9v17"
          stroke="#1F4E5F"
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
        />
      </svg>
      <span className={`text-xl font-bold tracking-tight ${claro ? 'text-white' : 'text-tinta-800'}`}>
        DBee<span className="text-mel-600">AS</span>
      </span>
    </span>
  )
}

type CampoProps = InputHTMLAttributes<HTMLInputElement> & { rotulo: string; dica?: string }

export function Campo({ rotulo, dica, className = '', ...props }: CampoProps) {
  const id = useId()
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-tinta-800">
        {rotulo}
      </label>
      <input
        id={id}
        className="w-full rounded-lg border border-tinta-100 bg-white px-3 py-2.5 text-base text-tinta-900 shadow-sm placeholder:text-tinta-300 focus:border-mel-500 focus:outline-none focus:ring-2 focus:ring-mel-200 disabled:bg-tinta-50"
        {...props}
      />
      {dica && <p className="mt-1 text-xs text-tinta-500">{dica}</p>}
    </div>
  )
}

type AreaTextoProps = TextareaHTMLAttributes<HTMLTextAreaElement> & { rotulo: string; dica?: ReactNode }

export function AreaTexto({ rotulo, dica, className = '', ...props }: AreaTextoProps) {
  const id = useId()
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-tinta-800">
        {rotulo}
      </label>
      <textarea
        id={id}
        className="w-full rounded-lg border border-tinta-100 bg-white px-3 py-2.5 text-base leading-relaxed text-tinta-900 shadow-sm placeholder:text-tinta-300 focus:border-mel-500 focus:outline-none focus:ring-2 focus:ring-mel-200"
        {...props}
      />
      {dica && <p className="mt-1 text-xs text-tinta-500">{dica}</p>}
    </div>
  )
}

type SelecaoProps = SelectHTMLAttributes<HTMLSelectElement> & { rotulo: string; children: ReactNode }

export function Selecao({ rotulo, className = '', children, ...props }: SelecaoProps) {
  const id = useId()
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-tinta-800">
        {rotulo}
      </label>
      <select
        id={id}
        className="w-full rounded-lg border border-tinta-100 bg-white px-3 py-2.5 text-base text-tinta-900 shadow-sm focus:border-mel-500 focus:outline-none focus:ring-2 focus:ring-mel-200"
        {...props}
      >
        {children}
      </select>
    </div>
  )
}

type CaixaProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & { children: ReactNode }

export function Caixa({ children, ...props }: CaixaProps) {
  return (
    <label className="flex cursor-pointer items-start gap-3 text-sm text-tinta-800">
      <input
        type="checkbox"
        className="mt-0.5 h-4 w-4 shrink-0 rounded border-tinta-300 accent-mel-600"
        {...props}
      />
      <span>{children}</span>
    </label>
  )
}

const ESTILOS_BOTAO = {
  primario: 'bg-tinta-700 text-white hover:bg-tinta-800 disabled:bg-tinta-300',
  destaque: 'bg-mel-500 text-tinta-900 hover:bg-mel-400 disabled:bg-mel-200',
  secundario: 'border border-tinta-100 bg-white text-tinta-800 hover:bg-tinta-50 disabled:text-tinta-300',
  perigo: 'bg-red-700 text-white hover:bg-red-800 disabled:bg-red-300',
}

type BotaoProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: keyof typeof ESTILOS_BOTAO
  carregando?: boolean
}

export function Botao({ variante = 'primario', carregando, disabled, className = '', children, ...props }: BotaoProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors disabled:cursor-not-allowed ${ESTILOS_BOTAO[variante]} ${className}`}
      disabled={disabled || carregando}
      {...props}
    >
      {carregando && (
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden />
      )}
      {children}
    </button>
  )
}

export function Alerta({ tipo = 'erro', children }: { tipo?: 'erro' | 'sucesso' | 'info'; children: ReactNode }) {
  const estilos = {
    erro: 'border-red-200 bg-red-50 text-red-800',
    sucesso: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    info: 'border-tinta-100 bg-tinta-50 text-tinta-800',
  }
  return (
    <div role={tipo === 'erro' ? 'alert' : 'status'} className={`rounded-lg border px-4 py-3 text-sm ${estilos[tipo]}`}>
      {children}
    </div>
  )
}

export function Cartao({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-2xl border border-tinta-100 bg-white p-6 shadow-sm ${className}`}>{children}</section>
}

export function Carregando() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center" role="status">
      <span className="h-8 w-8 animate-spin rounded-full border-4 border-mel-500 border-t-transparent" />
      <span className="sr-only">Carregando…</span>
    </div>
  )
}
