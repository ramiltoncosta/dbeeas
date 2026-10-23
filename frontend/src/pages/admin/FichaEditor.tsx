/**
 * Edição da ficha de uma espécie (administrador).
 * A ficha só aparece para o público depois de publicada; até lá é um rascunho.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import TextoFormatado from '../../components/TextoFormatado'
import { Alerta, AreaTexto, Botao, Campo, Carregando } from '../../components/ui'
import { api, enviarArquivo, mensagemErro, urlArquivo } from '../../lib/api'
import type { Especie } from '../../lib/coletas'
import type { Ficha } from '../../lib/especies'

type Campos = Pick<Ficha, 'nome_popular' | 'autoria' | 'descricao' | 'caracteristicas' | 'distribuicao' | 'fontes' | 'credito_imagem'>

const VAZIO: Record<keyof Campos, string> = {
  nome_popular: '',
  autoria: '',
  descricao: '',
  caracteristicas: '',
  distribuicao: '',
  fontes: '',
  credito_imagem: '',
}

const AJUDA_FORMATO = (
  <>
    Linha em branco separa parágrafos. Comece a linha com “- ” para fazer uma lista. Use *itálico* para nomes científicos
    e **negrito** para destaques. Links (https://...) viram clicáveis.
  </>
)

export default function FichaEditor() {
  const { id = '' } = useParams()
  const cliente = useQueryClient()
  const arquivo = useRef<HTMLInputElement>(null)
  const [campos, setCampos] = useState(VAZIO)
  const [modo, setModo] = useState<'editar' | 'ver'>('editar')
  const [aviso, setAviso] = useState<string | null>(null)
  const [alterado, setAlterado] = useState(false)

  const especies = useQuery({ queryKey: ['especies'], queryFn: () => api<Especie[]>('/v1/especies') })
  const especie = especies.data?.find((e) => String(e.id) === id)
  const ficha = useQuery({ queryKey: ['ficha', id], queryFn: () => api<Ficha>(`/v1/admin/especies/${id}/ficha`) })

  // Preenche o formulário uma vez, quando a ficha chega do servidor.
  // (Trocar a imagem atualiza a ficha, mas não pode apagar o texto que está sendo escrito.)
  const preenchido = useRef(false)
  useEffect(() => {
    if (!ficha.data || preenchido.current) return
    preenchido.current = true
    const f = ficha.data
    setCampos(Object.fromEntries(Object.keys(VAZIO).map((k) => [k, f[k as keyof Campos] ?? ''])) as typeof VAZIO)
    setAlterado(false)
  }, [ficha.data])

  const atualizar = (f: Ficha) => {
    cliente.setQueryData(['ficha', id], f)
    cliente.invalidateQueries({ queryKey: ['especies'] })
    cliente.invalidateQueries({ queryKey: ['publico'] })
  }

  const salvar = useMutation({
    mutationFn: (publicada: boolean) =>
      api<Ficha>(`/v1/admin/especies/${id}/ficha`, { method: 'PUT', body: { ...campos, publicada } }),
    onSuccess: (f, publicada) => {
      atualizar(f)
      setAlterado(false)
      setAviso(publicada ? 'Ficha publicada. Já aparece no site.' : 'Rascunho salvo. O público ainda não vê esta versão.')
    },
  })
  const imagem = useMutation({
    mutationFn: (a: File | null) =>
      a
        ? enviarArquivo<Ficha>(`/v1/admin/especies/${id}/ficha/imagem`, 'arquivo', a)
        : api<Ficha>(`/v1/admin/especies/${id}/ficha/imagem`, { method: 'DELETE' }),
    onSuccess: atualizar,
  })

  // Avisa antes de sair da página com alterações não salvas
  useEffect(() => {
    if (!alterado) return
    const aoSair = (ev: BeforeUnloadEvent) => ev.preventDefault()
    window.addEventListener('beforeunload', aoSair)
    return () => window.removeEventListener('beforeunload', aoSair)
  }, [alterado])

  if (ficha.isLoading || especies.isLoading) return <Carregando />
  if (ficha.error) return <Alerta>{mensagemErro(ficha.error)}</Alerta>

  const mudar = (k: keyof Campos) => (ev: { target: { value: string } }) => {
    setCampos((c) => ({ ...c, [k]: ev.target.value }))
    setAlterado(true)
    setAviso(null)
  }
  const publicada = ficha.data?.publicada ?? false
  const nome = especie?.nome_cientifico ?? 'Espécie'

  return (
    <div className="space-y-6">
      <div>
        <Link to="/admin/especies" className="text-sm font-semibold text-tinta-500 hover:text-tinta-800">← Espécies e fichas</Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="font-display text-3xl font-bold italic text-tinta-900">{nome}</h1>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${publicada ? 'bg-emerald-50 text-emerald-800' : 'bg-mel-100 text-mel-700'}`}>
            {publicada ? 'Publicada' : 'Rascunho'}
          </span>
        </div>
        {ficha.data?.atualizado_em && (
          <p className="mt-1 text-xs text-tinta-500">
            Última alteração em {new Date(ficha.data.atualizado_em).toLocaleString('pt-BR')}
            {ficha.data.atualizado_por && ` por ${ficha.data.atualizado_por}`}.{' '}
            {publicada && (
              <Link to={`/especies/${id}`} className="font-semibold text-tinta-700 underline">Ver no site</Link>
            )}
          </p>
        )}
      </div>

      <div className="flex gap-1 rounded-lg border border-tinta-100 bg-white p-0.5 sm:w-fit" role="group" aria-label="Modo">
        {(['editar', 'ver'] as const).map((m) => (
          <button
            key={m}
            aria-pressed={modo === m}
            onClick={() => setModo(m)}
            className={`flex-1 whitespace-nowrap rounded-md px-4 py-1.5 text-sm font-semibold ${modo === m ? 'bg-tinta-700 text-white' : 'text-tinta-800 hover:bg-tinta-50'}`}
          >
            {m === 'editar' ? 'Editar' : 'Ver como vai ficar'}
          </button>
        ))}
      </div>

      {modo === 'editar' ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Campo rotulo="Nome popular" value={campos.nome_popular} onChange={mudar('nome_popular')} maxLength={200} />
              <Campo rotulo="Autoria" placeholder="ex.: Moure, 1970" value={campos.autoria} onChange={mudar('autoria')} maxLength={200} />
            </div>
            <AreaTexto rotulo="Descrição" rows={7} value={campos.descricao} onChange={mudar('descricao')} dica={<>O primeiro parágrafo aparece como resumo na lista de espécies. {AJUDA_FORMATO}</>} />
            <AreaTexto rotulo="Características" rows={6} value={campos.caracteristicas} onChange={mudar('caracteristicas')} placeholder={'- Característica da asa\n- Coloração'} />
            <AreaTexto rotulo="Distribuição" rows={5} value={campos.distribuicao} onChange={mudar('distribuicao')} dica="Os registros da plataforma por estado aparecem sozinhos ao lado do texto." />
            <AreaTexto rotulo="Fontes" rows={5} value={campos.fontes} onChange={mudar('fontes')} dica="Uma referência por linha." />
          </div>

          <aside className="space-y-3">
            <h2 className="text-sm font-semibold text-tinta-800">Imagem</h2>
            <div className="flex aspect-[16/9] items-center justify-center overflow-hidden rounded-xl border border-tinta-100 bg-tinta-50">
              {ficha.data?.url_imagem ? (
                <img src={urlArquivo(ficha.data.url_imagem)} alt="" className="h-full w-full object-contain" />
              ) : (
                <span className="text-xs text-tinta-500">Sem imagem</span>
              )}
            </div>
            <input
              ref={arquivo}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              aria-label="Escolher imagem"
              onChange={(ev) => {
                const a = ev.target.files?.[0]
                if (a) imagem.mutate(a)
                ev.target.value = ''
              }}
            />
            <div className="flex flex-wrap gap-2">
              <Botao variante="secundario" className="!py-1.5" carregando={imagem.isPending} onClick={() => arquivo.current?.click()}>
                {ficha.data?.url_imagem ? 'Trocar imagem' : 'Enviar imagem'}
              </Botao>
              {ficha.data?.url_imagem && (
                <Botao variante="secundario" className="!py-1.5" disabled={imagem.isPending} onClick={() => imagem.mutate(null)}>
                  Remover
                </Botao>
              )}
            </div>
            <p className="text-xs text-tinta-500">É reduzida para até 1600 px e perde a localização (GPS) da foto. Vale na hora, mesmo sem salvar.</p>
            {imagem.error && <Alerta>{mensagemErro(imagem.error)}</Alerta>}
            <Campo rotulo="Crédito da imagem" placeholder="ex.: Foto: Nome, instituição" value={campos.credito_imagem} onChange={mudar('credito_imagem')} maxLength={300} />
          </aside>
        </div>
      ) : (
        <div className="max-w-[68ch] space-y-6 rounded-2xl border border-tinta-100 bg-white p-6 leading-relaxed text-tinta-800">
          {(['descricao', 'caracteristicas', 'distribuicao'] as const).map((k) => (
            <section key={k}>
              <h2 className="font-display text-xl font-bold text-tinta-900">
                {{ descricao: 'Descrição', caracteristicas: 'Características', distribuicao: 'Distribuição' }[k]}
              </h2>
              {campos[k] ? <TextoFormatado texto={campos[k]} className="mt-2" /> : <p className="mt-2 text-sm text-tinta-300">Vazio</p>}
            </section>
          ))}
        </div>
      )}

      <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center gap-3 border-t border-tinta-100 bg-fundo/95 px-4 py-3 backdrop-blur">
        <Botao variante="secundario" carregando={salvar.isPending && salvar.variables === false} disabled={salvar.isPending} onClick={() => salvar.mutate(false)}>
          {publicada ? 'Despublicar e salvar como rascunho' : 'Salvar rascunho'}
        </Botao>
        <Botao variante="destaque" carregando={salvar.isPending && salvar.variables === true} disabled={salvar.isPending} onClick={() => salvar.mutate(true)}>
          {publicada ? 'Salvar e manter publicada' : 'Publicar'}
        </Botao>
        {alterado && !salvar.isPending && <span className="text-xs text-mel-700">Alterações não salvas</span>}
        {aviso && !alterado && <span role="status" className="text-sm text-emerald-800">{aviso}</span>}
      </div>
      {salvar.error && <Alerta>{mensagemErro(salvar.error)}</Alerta>}
    </div>
  )
}
