/** Catálogo das espécies que o DBeeAS reconhece (página aberta ao público). */
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import Asa from '../../components/Asa'
import { Alerta, Carregando } from '../../components/ui'
import { api, mensagemErro, urlArquivo } from '../../lib/api'
import type { EspecieResumo } from '../../lib/especies'

export default function Catalogo() {
  const lista = useQuery({
    queryKey: ['publico', 'especies'],
    queryFn: () => api<EspecieResumo[]>('/v1/publico/especies'),
  })

  return (
    <div className="space-y-8">
      <header className="max-w-2xl">
        <h1 className="font-display text-3xl font-bold text-tinta-900 sm:text-4xl">Espécies</h1>
        <p className="mt-2 text-tinta-500">
          As abelhas que o DBeeAS identifica pela asa. Cada ficha é escrita e revisada por especialistas.
        </p>
      </header>

      {lista.isLoading && <Carregando />}
      {lista.error && <Alerta>{mensagemErro(lista.error)}</Alerta>}

      <ul className="grid gap-4 sm:grid-cols-2">
        {lista.data?.map((e) => (
          <li key={e.id}>
            <Link
              to={`/especies/${e.id}`}
              className="flex h-full gap-4 rounded-2xl border border-tinta-100 bg-white p-4 transition-colors hover:border-mel-400"
            >
              <div className="flex h-24 w-32 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-tinta-50">
                {e.url_imagem ? (
                  <img src={urlArquivo(e.url_imagem)} alt="" className="h-full w-full object-cover" loading="lazy" />
                ) : (
                  <Asa className="w-28 opacity-60" />
                )}
              </div>
              <div className="min-w-0">
                <h2 className="font-display text-xl font-bold italic leading-tight text-tinta-900">{e.nome_cientifico}</h2>
                {(e.autoria || e.nome_popular) && (
                  <p className="mt-0.5 text-sm text-tinta-500">{[e.autoria, e.nome_popular].filter(Boolean).join(', ')}</p>
                )}
                <p className="mt-2 line-clamp-3 text-sm text-tinta-700">
                  {e.resumo ?? 'Ficha em preparação.'}
                </p>
                {e.ocorrencias > 0 && (
                  <p className="mt-2 text-xs text-tinta-500">
                    {e.ocorrencias.toLocaleString('pt-BR')} registro(s) na plataforma
                  </p>
                )}
              </div>
            </Link>
          </li>
        ))}
      </ul>
      {lista.data?.length === 0 && (
        <p className="text-sm text-tinta-500">
          A lista aparece quando o modelo de identificação for carregado pela primeira vez.
        </p>
      )}
    </div>
  )
}
