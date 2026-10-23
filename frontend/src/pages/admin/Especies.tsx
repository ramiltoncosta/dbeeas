/** Administração das espécies: fichas, quais são sensíveis e o tamanho da área aproximada no mapa. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Alerta, Carregando } from '../../components/ui'
import { api, mensagemErro } from '../../lib/api'
import type { Especie } from '../../lib/coletas'

const RAIOS = [5, 10, 20, 50]

export default function AdminEspecies() {
  const cliente = useQueryClient()
  const especies = useQuery({ queryKey: ['especies'], queryFn: () => api<Especie[]>('/v1/especies') })
  const alterar = useMutation({
    mutationFn: ({ id, dados }: { id: number; dados: Partial<Pick<Especie, 'sensivel' | 'raio_ofuscacao_km'>> }) =>
      api<Especie>(`/v1/admin/especies/${id}`, { method: 'PATCH', body: dados }),
    onSuccess: () => {
      cliente.invalidateQueries({ queryKey: ['especies'] })
      cliente.invalidateQueries({ queryKey: ['mapa'] })
    },
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-tinta-900">Espécies e fichas</h1>
        <p className="mt-1 max-w-3xl text-sm text-tinta-500">
          Marque como <strong>sensível</strong> as espécies ameaçadas ou visadas por coleta ilegal. No mapa, quem não é
          o dono da foto, pesquisador ou administrador verá só uma área aproximada do tamanho escolhido.
        </p>
        <p className="mt-2 max-w-3xl text-sm text-tinta-500">
          As <strong>fichas</strong> aparecem na página pública de espécies depois de publicadas.
        </p>
      </div>

      {(especies.error || alterar.error) && <Alerta>{mensagemErro(especies.error ?? alterar.error)}</Alerta>}
      {especies.isLoading && <Carregando />}

      {especies.data && (
        <div className="overflow-x-auto rounded-2xl border border-tinta-100 bg-white shadow-sm">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="bg-tinta-50 text-xs uppercase tracking-wide text-tinta-500">
              <tr>
                <th className="px-4 py-3">Espécie</th>
                <th className="px-4 py-3">Origem</th>
                <th className="px-4 py-3">Ficha</th>
                <th className="px-4 py-3">Sensível</th>
                <th className="px-4 py-3">Área aproximada</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-tinta-50">
              {especies.data.map((e) => (
                <tr key={e.id}>
                  <td className="px-4 py-3 font-semibold italic text-tinta-800">{e.nome_cientifico}</td>
                  <td className="px-4 py-3 text-tinta-500">
                    {e.reconhecida_pelo_modelo ? 'Reconhecida pelo modelo' : 'Informada por pesquisador'}
                  </td>
                  <td className="px-4 py-3">
                    <Link to={`/admin/especies/${e.id}/ficha`} className="font-semibold text-tinta-700 underline">
                      {e.ficha === null ? 'Escrever' : 'Editar'}
                    </Link>{' '}
                    <span className={`ml-1 rounded-full px-2 py-0.5 text-xs font-semibold ${
                      e.ficha === 'publicada' ? 'bg-emerald-50 text-emerald-800' : e.ficha === 'rascunho' ? 'bg-mel-100 text-mel-700' : 'bg-tinta-50 text-tinta-500'
                    }`}>
                      {e.ficha === 'publicada' ? 'Publicada' : e.ficha === 'rascunho' ? 'Rascunho' : 'Sem ficha'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <label className="inline-flex cursor-pointer items-center gap-2">
                      <input
                        type="checkbox"
                        className="h-4 w-4 accent-mel-600"
                        checked={e.sensivel}
                        disabled={alterar.isPending}
                        onChange={(ev) => alterar.mutate({ id: e.id, dados: { sensivel: ev.target.checked } })}
                      />
                      {e.sensivel ? 'Sim' : 'Não'}
                    </label>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      aria-label={`Área aproximada de ${e.nome_cientifico}`}
                      className="rounded-md border border-tinta-100 bg-white px-2 py-1 disabled:text-tinta-300"
                      value={e.raio_ofuscacao_km}
                      disabled={!e.sensivel || alterar.isPending}
                      onChange={(ev) => alterar.mutate({ id: e.id, dados: { raio_ofuscacao_km: Number(ev.target.value) } })}
                    >
                      {[...new Set([...RAIOS, e.raio_ofuscacao_km])].sort((a, b) => a - b).map((r) => (
                        <option key={r} value={r}>cerca de {r} km</option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
              {especies.data.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-tinta-500">
                    As espécies aparecem aqui quando o modelo processar as primeiras fotos.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
