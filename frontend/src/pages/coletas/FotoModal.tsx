/** Detalhes de uma foto: imagem com as caixas, resultado, local e sexo. */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import SeletorLocal from '../../components/SeletorLocal'
import { Alerta, Botao, Selecao } from '../../components/ui'
import { api, mensagemErro, urlArquivo } from '../../lib/api'
import { pct, SEXOS, type Foto, type Ponto, type Sexo } from '../../lib/coletas'

export function ImagemComCaixas({ foto }: { foto: Foto }) {
  const deteccoes = foto.identificacao?.deteccoes ?? []
  return (
    <div className="relative overflow-hidden rounded-lg bg-tinta-900">
      <img src={urlArquivo(foto.url_media ?? foto.url_miniatura)} alt={`Foto ${foto.nome_original}`} className="block h-auto w-full" />
      {/* As caixas usam o tamanho original da foto; o SVG escala junto com a imagem */}
      <svg viewBox={`0 0 ${foto.largura} ${foto.altura}`} className="pointer-events-none absolute inset-0 h-full w-full" preserveAspectRatio="none">
        {deteccoes.map((d, i) => (
          <g key={i}>
            <rect
              x={d.caixa.x1}
              y={d.caixa.y1}
              width={d.caixa.x2 - d.caixa.x1}
              height={d.caixa.y2 - d.caixa.y1}
              fill="none"
              stroke={i === 0 ? '#e0a23a' : '#8fb0bd'}
              strokeWidth={3}
              vectorEffect="non-scaling-stroke"
            />
          </g>
        ))}
      </svg>
    </div>
  )
}

export function Selo({ foto }: { foto: Foto }) {
  if (foto.status === 'na_fila') return <span className="rounded-full bg-tinta-50 px-2 py-0.5 text-xs font-semibold text-tinta-500">Na fila</span>
  if (foto.status === 'processando') return <span className="rounded-full bg-mel-100 px-2 py-0.5 text-xs font-semibold text-mel-700">Processando</span>
  if (foto.status === 'erro') return <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700">Erro</span>
  if (!foto.identificacao?.identificada)
    return <span className="rounded-full bg-tinta-100 px-2 py-0.5 text-xs font-semibold text-tinta-700">Não identificada</span>
  return <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-800">{pct(foto.identificacao.confianca)}</span>
}

interface Props {
  foto: Foto
  localColeta: Ponto | null
  aoFechar: () => void
}

export default function FotoModal({ foto, localColeta, aoFechar }: Props) {
  const cliente = useQueryClient()
  const [local, setLocal] = useState<Ponto | null>(foto.local)
  const [sexo, setSexo] = useState<Sexo | ''>(foto.sexo ?? '')
  const [confirmarExclusao, setConfirmarExclusao] = useState(false)

  useEffect(() => {
    const fechar = (e: KeyboardEvent) => e.key === 'Escape' && aoFechar()
    window.addEventListener('keydown', fechar)
    return () => window.removeEventListener('keydown', fechar)
  }, [aoFechar])

  const recarregar = () => {
    cliente.invalidateQueries({ queryKey: ['fotos', foto.coleta_id] })
    cliente.invalidateQueries({ queryKey: ['progresso', foto.coleta_id] })
    cliente.invalidateQueries({ queryKey: ['coletas'] })
  }

  const salvar = useMutation({
    mutationFn: () => api<Foto>(`/v1/fotos/${foto.id}`, { method: 'PATCH', body: { local, sexo: sexo || null } }),
    onSuccess: recarregar,
  })
  const reprocessar = useMutation({
    mutationFn: () => api<Foto>(`/v1/fotos/${foto.id}/reprocessar`, { method: 'POST' }),
    onSuccess: () => {
      recarregar()
      aoFechar()
    },
  })
  const excluir = useMutation({
    mutationFn: () => api(`/v1/fotos/${foto.id}`, { method: 'DELETE' }),
    onSuccess: () => {
      recarregar()
      aoFechar()
    },
  })

  const ident = foto.identificacao
  const erro = salvar.error || reprocessar.error || excluir.error
  const alterado = JSON.stringify(local) !== JSON.stringify(foto.local) || (sexo || null) !== foto.sexo

  return (
    <div className="fixed inset-0 z-[1000] flex items-start justify-center overflow-y-auto bg-tinta-900/60 p-4 sm:p-8" onClick={aoFechar}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Foto ${foto.nome_original}`}
        className="w-full max-w-5xl rounded-2xl bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-4 border-b border-tinta-100 px-5 py-3">
          <h2 className="truncate font-bold text-tinta-800">{foto.nome_original}</h2>
          <button onClick={aoFechar} className="rounded-lg p-1.5 text-tinta-500 hover:bg-tinta-50" aria-label="Fechar">
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" /></svg>
          </button>
        </div>

        <div className="grid gap-6 p-5 lg:grid-cols-[3fr_2fr]">
          <div className="space-y-3">
            <ImagemComCaixas foto={foto} />
            <a href={urlArquivo(foto.url_original)} target="_blank" rel="noreferrer" className="text-sm font-semibold text-tinta-700 underline">
              Abrir foto original
            </a>
          </div>

          <div className="space-y-5">
            {erro && <Alerta>{mensagemErro(erro)}</Alerta>}

            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-tinta-500">Resultado</h3>
              {foto.status === 'concluida' && ident ? (
                ident.identificada ? (
                  <>
                    <p className="mt-1 text-xl font-bold italic text-tinta-900">{ident.especie}</p>
                    <p className="text-sm text-tinta-500">Confiança do modelo: {pct(ident.confianca)}</p>
                  </>
                ) : (
                  <p className="mt-1 text-sm text-tinta-800">
                    Não foi possível identificar com segurança
                    {ident.deteccoes[0] && ` (mais provável: ${ident.deteccoes[0].especie}, ${pct(ident.deteccoes[0].confianca)})`}.
                  </p>
                )
              ) : (
                <div className="mt-1 flex items-center gap-2"><Selo foto={foto} /></div>
              )}
              {foto.status === 'erro' && (
                <div className="mt-2 space-y-2">
                  <p className="text-sm text-red-700">{foto.erro}</p>
                  <Botao variante="secundario" className="!py-1.5" carregando={reprocessar.isPending} onClick={() => reprocessar.mutate()}>
                    Tentar de novo
                  </Botao>
                </div>
              )}
              {ident?.versao_modelo && <p className="mt-1 text-xs text-tinta-300">Modelo {ident.versao_modelo}</p>}
            </section>

            <section className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-tinta-500">Localização</h3>
              <p className="text-xs text-tinta-500">
                {foto.origem_local === 'exif'
                  ? 'Lida do GPS da foto. Você pode corrigir clicando no mapa.'
                  : foto.local
                    ? 'Marcada manualmente.'
                    : localColeta
                      ? 'Sem localização própria: usa o ponto da coleta.'
                      : 'Sem localização. Marque no mapa.'}
              </p>
              <SeletorLocal valor={local ?? null} aoMudar={setLocal} altura="h-56" />
            </section>

            <Selecao rotulo="Sexo do espécime" value={sexo} onChange={(e) => setSexo(e.target.value as Sexo | '')}>
              <option value="">Não informado</option>
              {Object.entries(SEXOS).map(([v, n]) => <option key={v} value={v}>{n}</option>)}
            </Selecao>

            {foto.data_captura && (
              <p className="text-sm text-tinta-500">Foto tirada em {new Date(foto.data_captura).toLocaleString('pt-BR')}</p>
            )}

            <div className="flex flex-wrap gap-3 border-t border-tinta-100 pt-4">
              <Botao disabled={!alterado} carregando={salvar.isPending} onClick={() => salvar.mutate()}>
                {salvar.isSuccess && !alterado ? 'Salvo' : 'Salvar'}
              </Botao>
              {confirmarExclusao ? (
                <Botao variante="perigo" carregando={excluir.isPending} onClick={() => excluir.mutate()}>
                  Confirmar exclusão
                </Botao>
              ) : (
                <Botao variante="secundario" onClick={() => setConfirmarExclusao(true)}>Excluir foto</Botao>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
