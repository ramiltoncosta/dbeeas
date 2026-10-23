import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Alerta, Botao, Campo, Carregando, Selecao } from '../../components/ui'
import { api, ErroApi, NOMES_PERFIL, type Perfil, type UsuarioAdmin } from '../../lib/api'
import { useAuth } from '../../lib/auth'

interface Pagina {
  itens: UsuarioAdmin[]
  total: number
  pagina: number
  por_pagina: number
}

const data = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('pt-BR') : '—')

export default function AdminUsuarios() {
  const { usuario: eu } = useAuth()
  const cliente = useQueryClient()
  const [busca, setBusca] = useState('')
  const [perfil, setPerfil] = useState('')
  const [aguardando, setAguardando] = useState(false)
  const [pagina, setPagina] = useState(1)

  const params = new URLSearchParams({ pagina: String(pagina), por_pagina: '20' })
  if (busca.trim()) params.set('busca', busca.trim())
  if (perfil) params.set('perfil', perfil)
  if (aguardando) params.set('aguardando_aprovacao', 'true')

  const consulta = useQuery({
    queryKey: ['admin-usuarios', params.toString()],
    queryFn: () => api<Pagina>(`/v1/admin/usuarios?${params}`),
    placeholderData: keepPreviousData,
  })

  const alterar = useMutation({
    mutationFn: ({ id, dados }: { id: string; dados: Partial<Pick<UsuarioAdmin, 'perfil' | 'ativo' | 'perfil_aprovado'>> }) =>
      api<UsuarioAdmin>(`/v1/admin/usuarios/${id}`, { method: 'PATCH', body: dados }),
    onSuccess: () => cliente.invalidateQueries({ queryKey: ['admin-usuarios'] }),
  })

  const total = consulta.data?.total ?? 0
  const paginas = Math.max(1, Math.ceil(total / 20))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-tinta-900">Usuários</h1>
        <p className="mt-1 text-sm text-tinta-500">{total} usuário(s) encontrado(s)</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-[1fr_200px_auto] sm:items-end">
        <Campo rotulo="Buscar" placeholder="Nome, e-mail ou instituição" value={busca} onChange={(e) => { setBusca(e.target.value); setPagina(1) }} />
        <Selecao rotulo="Perfil" value={perfil} onChange={(e) => { setPerfil(e.target.value); setPagina(1) }}>
          <option value="">Todos</option>
          {Object.entries(NOMES_PERFIL).map(([valor, nome]) => (
            <option key={valor} value={valor}>{nome}</option>
          ))}
        </Selecao>
        <label className="flex items-center gap-2 pb-3 text-sm text-tinta-800">
          <input type="checkbox" className="accent-mel-600" checked={aguardando} onChange={(e) => { setAguardando(e.target.checked); setPagina(1) }} />
          Aguardando aprovação
        </label>
      </div>

      {alterar.error && <Alerta>{alterar.error instanceof ErroApi ? alterar.error.message : 'Erro ao salvar.'}</Alerta>}
      {consulta.error && <Alerta>{consulta.error instanceof ErroApi ? consulta.error.message : 'Erro ao carregar.'}</Alerta>}
      {consulta.isLoading && <Carregando />}

      {consulta.data && (
        <div className="overflow-x-auto rounded-2xl border border-tinta-100 bg-white shadow-sm">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="bg-tinta-50 text-xs uppercase tracking-wide text-tinta-500">
              <tr>
                <th className="px-4 py-3">Usuário</th>
                <th className="px-4 py-3">Perfil</th>
                <th className="px-4 py-3">Cadastro</th>
                <th className="px-4 py-3">Último acesso</th>
                <th className="px-4 py-3">Situação</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-tinta-50">
              {consulta.data.itens.map((u) => {
                const souEu = u.id === eu?.id
                return (
                  <tr key={u.id} className={u.ativo ? '' : 'bg-tinta-50/60 text-tinta-500'}>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-tinta-800">{u.nome}{souEu && ' (você)'}</p>
                      <p className="text-xs text-tinta-500">{u.email}</p>
                      {u.instituicao && <p className="text-xs text-tinta-500">{u.instituicao}</p>}
                    </td>
                    <td className="px-4 py-3">
                      <select
                        aria-label={`Perfil de ${u.nome}`}
                        className="rounded-md border border-tinta-100 bg-white px-2 py-1 text-sm"
                        value={u.perfil}
                        disabled={souEu || alterar.isPending}
                        onChange={(e) => alterar.mutate({ id: u.id, dados: { perfil: e.target.value as Perfil } })}
                      >
                        {Object.entries(NOMES_PERFIL).map(([valor, nome]) => (
                          <option key={valor} value={valor}>{nome}</option>
                        ))}
                      </select>
                      {u.perfil === 'pesquisador' && !u.perfil_aprovado && (
                        <button
                          className="mt-1 block text-xs font-semibold text-mel-700 hover:underline"
                          onClick={() => alterar.mutate({ id: u.id, dados: { perfil_aprovado: true } })}
                        >
                          Aprovar pesquisador
                        </button>
                      )}
                    </td>
                    <td className="px-4 py-3">{data(u.criado_em)}</td>
                    <td className="px-4 py-3">{data(u.ultimo_login_em)}</td>
                    <td className="px-4 py-3">
                      <Botao
                        variante={u.ativo ? 'secundario' : 'primario'}
                        className="!px-3 !py-1.5 text-xs"
                        disabled={souEu || alterar.isPending}
                        onClick={() => alterar.mutate({ id: u.id, dados: { ativo: !u.ativo } })}
                      >
                        {u.ativo ? 'Desativar' : 'Reativar'}
                      </Botao>
                    </td>
                  </tr>
                )
              })}
              {consulta.data.itens.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-tinta-500">Nenhum usuário encontrado.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {paginas > 1 && (
        <div className="flex items-center justify-center gap-3">
          <Botao variante="secundario" disabled={pagina <= 1} onClick={() => setPagina((p) => p - 1)}>Anterior</Botao>
          <span className="text-sm text-tinta-500">Página {pagina} de {paginas}</span>
          <Botao variante="secundario" disabled={pagina >= paginas} onClick={() => setPagina((p) => p + 1)}>Próxima</Botao>
        </div>
      )}
    </div>
  )
}
