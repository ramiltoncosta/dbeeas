/** Mensagens enviadas pelo formulário de contato da página pública. */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Alerta, Botao, Carregando } from '../../components/ui'
import { api, mensagemErro } from '../../lib/api'

interface Mensagem {
  id: string
  nome: string
  email: string
  instituicao: string | null
  assunto: string
  mensagem: string
  respondida: boolean
  criado_em: string
}

const ASSUNTOS: Record<string, string> = {
  duvida: 'Dúvida',
  planos: 'Planos e assinaturas',
  institucional: 'Uso institucional',
  parceria: 'Parceria',
  imprensa: 'Imprensa',
  outro: 'Outro assunto',
}

export default function AdminMensagens() {
  const cliente = useQueryClient()
  const [pendentes, setPendentes] = useState(true)
  const lista = useQuery({
    queryKey: ['mensagens', pendentes],
    queryFn: () =>
      api<{ itens: Mensagem[]; total: number; nao_respondidas: number }>(
        `/v1/admin/mensagens?por_pagina=100&somente_nao_respondidas=${pendentes}`,
      ),
    placeholderData: keepPreviousData,
  })
  const marcar = useMutation({
    mutationFn: ({ id, respondida }: { id: string; respondida: boolean }) =>
      api(`/v1/admin/mensagens/${id}`, { method: 'PATCH', body: { respondida } }),
    onSuccess: () => {
      cliente.invalidateQueries({ queryKey: ['mensagens'] })
      cliente.invalidateQueries({ queryKey: ['painel'] })
    },
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-tinta-900">Mensagens de contato</h1>
          <p className="mt-1 text-sm text-tinta-500">
            Enviadas pelo formulário da página inicial. Responda pelo seu e-mail e marque como respondida.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm text-tinta-800">
          <input type="checkbox" className="h-4 w-4 accent-mel-600" checked={pendentes} onChange={(e) => setPendentes(e.target.checked)} />
          Só as sem resposta
        </label>
      </div>
      {lista.isLoading && <Carregando />}
      {(lista.error || marcar.error) && <Alerta>{mensagemErro(lista.error ?? marcar.error)}</Alerta>}
      {lista.data && lista.data.itens.length === 0 && (
        <p className="rounded-2xl border border-dashed border-tinta-300 p-6 text-center text-sm text-tinta-500">
          {pendentes ? 'Nenhuma mensagem esperando resposta.' : 'Nenhuma mensagem recebida ainda.'}
        </p>
      )}
      <ul className="space-y-3">
        {lista.data?.itens.map((m) => (
          <li key={m.id} className={`rounded-2xl border bg-white p-5 ${m.respondida ? 'border-tinta-100 opacity-75' : 'border-mel-200'}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-tinta-900">
                  {m.nome}
                  {m.instituicao && <span className="font-normal text-tinta-500">, {m.instituicao}</span>}
                </p>
                <p className="text-sm">
                  <a href={`mailto:${m.email}?subject=${encodeURIComponent('Re: contato DBeeAS')}`} className="text-tinta-700 underline">
                    {m.email}
                  </a>
                  <span className="text-tinta-500"> em {new Date(m.criado_em).toLocaleString('pt-BR')}</span>
                </p>
              </div>
              <span className="rounded-full bg-tinta-50 px-2.5 py-0.5 text-xs font-semibold text-tinta-700">{ASSUNTOS[m.assunto] ?? m.assunto}</span>
            </div>
            <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-tinta-800">{m.mensagem}</p>
            <Botao
              variante="secundario"
              className="mt-3 !py-1.5"
              disabled={marcar.isPending}
              onClick={() => marcar.mutate({ id: m.id, respondida: !m.respondida })}
            >
              {m.respondida ? 'Marcar como sem resposta' : 'Marcar como respondida'}
            </Botao>
          </li>
        ))}
      </ul>
    </div>
  )
}
