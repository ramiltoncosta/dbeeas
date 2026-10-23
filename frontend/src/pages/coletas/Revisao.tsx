/** Revisão da foto por uma pessoa: confirmar, corrigir, marcar como não identificável ou desfazer. */
import { useMutation, useQuery } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { Alerta, Botao } from '../../components/ui'
import { api, mensagemErro, NOMES_PERFIL, type Perfil } from '../../lib/api'
import { ACOES_REVISAO, pct, type Especie, type Foto } from '../../lib/coletas'

type Acao = 'confirmar' | 'corrigir' | 'nao_identificavel' | 'restaurar'

export default function Revisao({ foto, aoRevisar }: { foto: Foto; aoRevisar: (f: Foto) => void }) {
  const idLista = useId()
  const [modo, setModo] = useState<'corrigir' | 'nao_identificavel' | null>(null)
  const [especie, setEspecie] = useState('')
  const [observacao, setObservacao] = useState('')

  const especies = useQuery({
    queryKey: ['especies'],
    queryFn: () => api<Especie[]>('/v1/especies'),
    staleTime: 5 * 60 * 1000,
  })

  const revisar = useMutation({
    mutationFn: (acao: Acao) =>
      api<Foto>(`/v1/fotos/${foto.id}/revisao`, {
        method: 'POST',
        body: {
          acao,
          especie: acao === 'corrigir' ? especie : null,
          observacao: observacao || null,
        },
      }),
    onSuccess: (f) => {
      setModo(null)
      setEspecie('')
      setObservacao('')
      aoRevisar(f)
    },
  })

  if (foto.status !== 'concluida') return null
  const ident = foto.identificacao
  const rev = foto.revisao

  return (
    <section className="space-y-3 rounded-xl border border-tinta-100 bg-tinta-50/50 p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-tinta-500">Revisão</h3>

      {foto.revisada && rev ? (
        <div className="text-sm text-tinta-800">
          <p>
            <span className="font-semibold">{ACOES_REVISAO[rev.acao]}</span>
            {rev.revisor ? ` por ${rev.revisor}` : ''}
            {` (${NOMES_PERFIL[rev.perfil_revisor as Perfil] ?? rev.perfil_revisor})`} em{' '}
            {new Date(rev.criado_em).toLocaleDateString('pt-BR')}.
          </p>
          {rev.observacao && <p className="mt-1 text-tinta-500">“{rev.observacao}”</p>}
          {ident && (
            <p className="mt-1 text-xs text-tinta-500">
              O modelo indicou {ident.identificada ? <em>{ident.especie}</em> : 'nenhuma espécie com segurança'}
              {ident.confianca != null && ` (${pct(ident.confianca)})`}.
            </p>
          )}
        </div>
      ) : (
        <p className="text-sm text-tinta-500">
          {foto.especie ? 'O resultado está certo?' : 'Você sabe qual é a espécie?'} Sua revisão melhora os dados da
          coleta e ajuda a treinar o modelo.
        </p>
      )}

      {revisar.error && <Alerta>{mensagemErro(revisar.error)}</Alerta>}

      {modo === null && (
        <div className="flex flex-wrap gap-2">
          {foto.especie && !(foto.revisada && rev?.acao === 'confirmou') && (
            <Botao variante="primario" className="!py-1.5" carregando={revisar.isPending} onClick={() => revisar.mutate('confirmar')}>
              ✓ Confirmar
            </Botao>
          )}
          <Botao variante="secundario" className="!py-1.5" onClick={() => setModo('corrigir')}>
            {foto.especie ? 'Corrigir espécie' : 'Informar espécie'}
          </Botao>
          {!(foto.revisada && rev?.acao === 'nao_identificavel') && (
            <Botao variante="secundario" className="!py-1.5" onClick={() => setModo('nao_identificavel')}>
              Não identificável
            </Botao>
          )}
          {foto.revisada && (
            <Botao variante="secundario" className="!py-1.5" carregando={revisar.isPending} onClick={() => revisar.mutate('restaurar')}>
              Desfazer revisão
            </Botao>
          )}
        </div>
      )}

      {modo !== null && (
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            revisar.mutate(modo)
          }}
        >
          {modo === 'corrigir' && (
            <div>
              <label htmlFor={`${idLista}-esp`} className="mb-1 block text-sm font-medium text-tinta-800">
                Espécie correta
              </label>
              <input
                id={`${idLista}-esp`}
                list={idLista}
                required
                autoFocus
                placeholder="Ex.: Euglossa cognata"
                className="w-full rounded-lg border border-tinta-100 bg-white px-3 py-2 text-base italic shadow-sm focus:border-mel-500 focus:outline-none focus:ring-2 focus:ring-mel-200"
                value={especie}
                onChange={(e) => setEspecie(e.target.value)}
              />
              <datalist id={idLista}>
                {especies.data?.map((e) => <option key={e.id} value={e.nome_cientifico} />)}
              </datalist>
              <p className="mt-1 text-xs text-tinta-500">
                Escolha da lista ou digite o nome científico (use “sp.” se a espécie for desconhecida).
              </p>
            </div>
          )}
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-tinta-800">Observação (opcional)</span>
            <textarea
              rows={2}
              maxLength={2000}
              placeholder={modo === 'nao_identificavel' ? 'Ex.: asa danificada, foto desfocada' : 'Ex.: conferido na lupa'}
              className="w-full rounded-lg border border-tinta-100 bg-white px-3 py-2 text-sm shadow-sm focus:border-mel-500 focus:outline-none focus:ring-2 focus:ring-mel-200"
              value={observacao}
              onChange={(e) => setObservacao(e.target.value)}
            />
          </label>
          <div className="flex gap-2">
            <Botao type="submit" className="!py-1.5" carregando={revisar.isPending}>
              {modo === 'corrigir' ? 'Salvar correção' : 'Marcar como não identificável'}
            </Botao>
            <Botao type="button" variante="secundario" className="!py-1.5" onClick={() => setModo(null)}>
              Cancelar
            </Botao>
          </div>
        </form>
      )}
    </section>
  )
}
