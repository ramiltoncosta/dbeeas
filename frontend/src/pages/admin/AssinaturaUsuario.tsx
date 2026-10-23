/**
 * Janela do administrador para ver e mudar o plano de um usuário.
 * Enquanto não há cobrança automática, é aqui que o plano é ativado depois do pagamento.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Alerta, AreaTexto, Botao, Campo, Carregando, Selecao } from '../../components/ui'
import { api, mensagemErro, type UsuarioAdmin } from '../../lib/api'
import { COR_STATUS, dataCurta, NOMES_STATUS, type Assinatura, type MeuPlano, type Plano } from '../../lib/planos'

const PRAZOS = [
  ['30', '30 dias'],
  ['90', '3 meses'],
  ['365', '1 ano'],
  ['sem', 'Sem prazo'],
  ['data', 'Até uma data'],
] as const

export default function AssinaturaUsuario({ usuario, aoFechar }: { usuario: UsuarioAdmin; aoFechar: () => void }) {
  const cliente = useQueryClient()
  const planos = useQuery({ queryKey: ['admin-planos'], queryFn: () => api<Plano[]>('/v1/admin/planos') })
  const situacao = useQuery({ queryKey: ['admin-plano', usuario.id], queryFn: () => api<MeuPlano>(`/v1/admin/usuarios/${usuario.id}/plano`) })
  const historico = useQuery({
    queryKey: ['admin-assinaturas', usuario.id],
    queryFn: () => api<Assinatura[]>(`/v1/admin/usuarios/${usuario.id}/assinaturas`),
  })

  const [planoId, setPlanoId] = useState('')
  const [status, setStatus] = useState('ativa')
  const [prazo, setPrazo] = useState<string>('30')
  const [data, setData] = useState('')
  const [observacao, setObservacao] = useState('')
  const [salvo, setSalvo] = useState(false)

  // Começa com o plano pedido (se houver) ou o atual
  useEffect(() => {
    if (planoId || !situacao.data) return
    const s = situacao.data
    setPlanoId(String(s.pedido?.plano.id ?? s.plano?.id ?? ''))
  }, [situacao.data, planoId])

  // Fecha com Esc
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => e.key === 'Escape' && aoFechar()
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [aoFechar])

  const salvar = useMutation({
    mutationFn: () =>
      api<MeuPlano>(`/v1/admin/usuarios/${usuario.id}/assinaturas`, {
        method: 'POST',
        body: {
          plano_id: Number(planoId),
          status,
          dias: /^\d+$/.test(prazo) ? Number(prazo) : null,
          fim: prazo === 'data' && data ? new Date(`${data}T23:59:59`).toISOString() : null,
          observacao: observacao.trim() || null,
        },
      }),
    onSuccess: (s) => {
      cliente.setQueryData(['admin-plano', usuario.id], s)
      cliente.invalidateQueries({ queryKey: ['admin-assinaturas', usuario.id] })
      cliente.invalidateQueries({ queryKey: ['admin-usuarios'] })
      setObservacao('')
      setSalvo(true)
    },
  })

  const s = situacao.data
  return (
    <div className="fixed inset-0 z-[1000] flex items-end justify-center bg-tinta-900/50 sm:items-center sm:p-4" onClick={aoFechar}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="titulo-assinatura"
        className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-t-2xl bg-white p-6 shadow-xl sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="titulo-assinatura" className="text-xl font-bold text-tinta-900">Plano de {usuario.nome}</h2>
            <p className="text-sm text-tinta-500">{usuario.email}</p>
          </div>
          <button onClick={aoFechar} className="rounded-lg px-2 py-1 text-tinta-500 hover:bg-tinta-50" aria-label="Fechar">✕</button>
        </div>

        {situacao.isLoading && <Carregando />}
        {s && (
          <div className="mt-4 rounded-xl bg-tinta-50/70 p-4 text-sm">
            <p className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-tinta-900">{s.plano?.nome ?? 'Sem plano'}</span>
              <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${COR_STATUS[s.status]}`}>{NOMES_STATUS[s.status]}</span>
              {s.assinatura?.fim && <span className="text-tinta-500">até {dataCurta(s.assinatura.fim)}</span>}
            </p>
            <p className="mt-1 text-tinta-700">
              Uso no mês: {s.uso.usadas}
              {s.uso.limite != null && ` de ${s.uso.limite}`} foto(s)
            </p>
            {s.pedido && (
              <p className="mt-1 font-semibold text-mel-700">
                Pediu o plano {s.pedido.plano.nome} em {dataCurta(s.pedido.criado_em)}.
              </p>
            )}
          </div>
        )}

        <form
          className="mt-5 grid gap-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault()
            setSalvo(false)
            salvar.mutate()
          }}
        >
          <Selecao rotulo="Plano" value={planoId} onChange={(e) => setPlanoId(e.target.value)} required>
            <option value="" disabled>Escolha</option>
            {planos.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nome}{p.publico ? '' : ' (oculto)'}
              </option>
            ))}
          </Selecao>
          <Selecao rotulo="Situação" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="ativa">Ativa (pagamento confirmado)</option>
            <option value="teste">Teste gratuito</option>
            <option value="suspensa">Suspensa (bloqueia o envio)</option>
            <option value="cancelada">Cancelada (bloqueia o envio)</option>
          </Selecao>
          <Selecao rotulo="Validade" value={prazo} onChange={(e) => setPrazo(e.target.value)}>
            {PRAZOS.map(([v, n]) => (
              <option key={v} value={v}>{n}</option>
            ))}
          </Selecao>
          {prazo === 'data' ? (
            <Campo rotulo="Válido até" type="date" value={data} onChange={(e) => setData(e.target.value)} required />
          ) : (
            <div />
          )}
          <AreaTexto
            rotulo="Observação (só a equipe vê)"
            rows={2}
            className="sm:col-span-2"
            placeholder="ex.: pagamento por PIX em 23/10"
            value={observacao}
            onChange={(e) => setObservacao(e.target.value)}
            maxLength={1000}
          />
          <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
            <Botao type="submit" carregando={salvar.isPending} disabled={!planoId}>Salvar plano</Botao>
            {salvo && <span role="status" className="text-sm text-emerald-800">Plano salvo. Já vale para o envio de fotos.</span>}
          </div>
          {salvar.error && <div className="sm:col-span-2"><Alerta>{mensagemErro(salvar.error)}</Alerta></div>}
        </form>

        <section className="mt-6">
          <h3 className="text-sm font-semibold text-tinta-800">Histórico</h3>
          <ul className="mt-2 divide-y divide-tinta-100 text-sm">
            {historico.data?.map((a) => (
              <li key={a.id} className="py-2">
                <p>
                  <span className="font-semibold text-tinta-800">{a.plano.nome}</span>{' '}
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${COR_STATUS[a.status]}`}>
                    {a.status === 'pendente' ? 'Pedido' : NOMES_STATUS[a.status]}
                  </span>
                  <span className="text-tinta-500"> em {new Date(a.criado_em).toLocaleString('pt-BR')}</span>
                </p>
                <p className="text-xs text-tinta-500">
                  {[
                    a.fim && `válido até ${dataCurta(a.fim)}`,
                    a.alterado_por && `por ${a.alterado_por}`,
                    a.origem !== 'manual' && `via ${a.origem}`,
                    a.observacao,
                  ]
                    .filter(Boolean)
                    .join('; ')}
                </p>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
