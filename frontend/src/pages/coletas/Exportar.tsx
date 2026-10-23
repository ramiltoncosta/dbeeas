/**
 * Exportação da coleta: ZIP com as fotos separadas em pastas por espécie
 * e a planilha ocorrencias.csv no padrão Darwin Core.
 *
 * O arquivo é gerado no servidor, em segundo plano. Enquanto isso, a tela
 * consulta o status a cada 2 segundos.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Alerta, Botao } from '../../components/ui'
import { api, mensagemErro, urlArquivo } from '../../lib/api'
import type { Contagem } from '../../lib/coletas'

type StatusExportacao = 'na_fila' | 'gerando' | 'pronta' | 'erro' | 'expirada'
type TipoImagem = 'original' | 'reduzida'

interface Exportacao {
  id: string
  tipo_imagem: TipoImagem
  status: StatusExportacao
  total_fotos: number | null
  tamanho_bytes: number | null
  erro: string | null
  criado_em: string
  concluida_em: string | null
  expira_em: string | null
  url_download: string | null
}

const TIPOS: Record<TipoImagem, { nome: string; dica: string }> = {
  original: { nome: 'Fotos originais', dica: 'Sem alteração, com toda a resolução. Arquivo maior.' },
  reduzida: { nome: 'Fotos reduzidas', dica: 'Até 1600 px. Bem menor, bom para compartilhar.' },
}

const NOME_STATUS: Record<StatusExportacao, string> = {
  na_fila: 'Na fila',
  gerando: 'Gerando…',
  pronta: 'Pronta',
  erro: 'Erro',
  expirada: 'Expirada',
}

function tamanho(bytes: number | null) {
  if (bytes == null) return ''
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1).replace('.', ',')} MB`
  return `${(bytes / 1024 ** 3).toFixed(2).replace('.', ',')} GB`
}

const dataHora = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : ''

const emAndamento = (e: Exportacao) => e.status === 'na_fila' || e.status === 'gerando'

export default function Exportar({ coletaId, progresso }: { coletaId: string; progresso?: Contagem }) {
  const cliente = useQueryClient()
  const [tipo, setTipo] = useState<TipoImagem>('original')
  const [erroBaixar, setErroBaixar] = useState<string | null>(null)

  const lista = useQuery({
    queryKey: ['exportacoes', coletaId],
    queryFn: () => api<Exportacao[]>(`/v1/coletas/${coletaId}/exportacoes`),
    refetchInterval: (q) => (q.state.data?.some(emAndamento) ? 2000 : false),
  })

  const pedir = useMutation({
    mutationFn: () =>
      api<Exportacao>(`/v1/coletas/${coletaId}/exportacoes`, { method: 'POST', body: { tipo_imagem: tipo } }),
    onSuccess: () => cliente.invalidateQueries({ queryKey: ['exportacoes', coletaId] }),
  })

  // Pede um link novo na hora de baixar (o link do status pode ter vencido)
  const baixar = async (e: Exportacao) => {
    setErroBaixar(null)
    try {
      const atual = await api<Exportacao>(`/v1/exportacoes/${e.id}`)
      if (!atual.url_download) {
        cliente.invalidateQueries({ queryKey: ['exportacoes', coletaId] })
        setErroBaixar('Este arquivo expirou. Gere um novo.')
        return
      }
      window.location.assign(urlArquivo(atual.url_download)!)
    } catch (err) {
      setErroBaixar(mensagemErro(err))
    }
  }

  const itens = lista.data ?? []
  const gerando = itens.some(emAndamento)
  const pendentes = progresso ? progresso.na_fila + progresso.processando : 0
  const comErro = progresso?.erro ?? 0

  return (
    <section className="rounded-2xl border border-tinta-100 bg-white p-5 shadow-sm" aria-labelledby="titulo-exportar">
      <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
        <div>
          <h2 id="titulo-exportar" className="text-lg font-bold text-tinta-800">Exportar amostra digital</h2>
          <p className="mt-1 text-sm text-tinta-500">
            Um arquivo ZIP com uma pasta por espécie e a planilha <span className="font-medium text-tinta-700">ocorrencias.csv</span>{' '}
            no padrão Darwin Core (aceito pelo SiBBr e pelo GBIF).
          </p>

          <fieldset className="mt-4 grid gap-2 sm:grid-cols-2">
            <legend className="sr-only">Imagens no arquivo</legend>
            {(Object.keys(TIPOS) as TipoImagem[]).map((t) => (
              <label
                key={t}
                className={`flex cursor-pointer gap-3 rounded-xl border p-3 text-sm transition ${tipo === t ? 'border-mel-500 bg-mel-50' : 'border-tinta-100 hover:bg-tinta-50'}`}
              >
                <input
                  type="radio"
                  name="tipo-imagem"
                  value={t}
                  checked={tipo === t}
                  onChange={() => setTipo(t)}
                  className="mt-0.5 h-4 w-4 accent-mel-600"
                />
                <span>
                  <span className="block font-semibold text-tinta-800">{TIPOS[t].nome}</span>
                  <span className="text-xs text-tinta-500">{TIPOS[t].dica}</span>
                </span>
              </label>
            ))}
          </fieldset>

          {pendentes > 0 && (
            <p className="mt-3 text-xs text-mel-700">
              {pendentes} foto(s) ainda em processamento. Se exportar agora, elas vão para a pasta “nao_processadas”.
            </p>
          )}
          {comErro > 0 && pendentes === 0 && (
            <p className="mt-3 text-xs text-tinta-500">
              {comErro} foto(s) com erro vão para a pasta “nao_processadas”.
            </p>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Botao variante="destaque" carregando={pedir.isPending} disabled={gerando} onClick={() => pedir.mutate()}>
              {gerando ? 'Gerando arquivo…' : 'Gerar arquivo ZIP'}
            </Botao>
            {gerando && <span className="text-xs text-tinta-500">Pode sair da página: avisamos por e-mail quando ficar pronto.</span>}
          </div>
          {pedir.error && <div className="mt-3"><Alerta>{mensagemErro(pedir.error)}</Alerta></div>}
        </div>

        <div className="lg:border-l lg:border-tinta-100 lg:pl-5">
          <h3 className="text-sm font-semibold text-tinta-700">Arquivos gerados</h3>
          {erroBaixar && <div className="mt-2"><Alerta>{erroBaixar}</Alerta></div>}
          {itens.length === 0 ? (
            <p className="mt-2 text-sm text-tinta-500">Nenhum ainda. Os arquivos ficam disponíveis por 7 dias.</p>
          ) : (
            <ul className="mt-2 divide-y divide-tinta-100">
              {itens.slice(0, 5).map((e) => (
                <li key={e.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5 text-sm">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-tinta-800">
                      {TIPOS[e.tipo_imagem].nome}
                      {e.total_fotos != null && <span className="font-normal text-tinta-500"> · {e.total_fotos} foto(s)</span>}
                      {e.tamanho_bytes != null && <span className="font-normal text-tinta-500"> · {tamanho(e.tamanho_bytes)}</span>}
                    </p>
                    <p className="text-xs text-tinta-500">
                      Pedido em {dataHora(e.criado_em)}
                      {e.status === 'pronta' && e.expira_em && <> · disponível até {dataHora(e.expira_em)}</>}
                      {e.status === 'erro' && e.erro && <span className="text-red-700"> · {e.erro}</span>}
                    </p>
                  </div>
                  {e.status === 'pronta' ? (
                    <Botao className="!py-1.5" onClick={() => baixar(e)}>Baixar</Botao>
                  ) : (
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
                        e.status === 'erro'
                          ? 'bg-red-50 text-red-800'
                          : emAndamento(e)
                            ? 'bg-mel-100 text-mel-700'
                            : 'bg-tinta-50 text-tinta-500'
                      }`}
                    >
                      {emAndamento(e) && (
                        <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden />
                      )}
                      {NOME_STATUS[e.status]}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}
