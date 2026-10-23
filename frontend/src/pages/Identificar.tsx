/**
 * Identificação rápida: uma ou várias fotos, sem criar coleta.
 * As fotos não ficam guardadas; se quiser guardar, dá para salvar tudo numa nova coleta.
 */
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Alerta, Botao } from '../components/ui'
import { API_URL, api, ErroApi, mensagemErro, obterToken, renovarSessao } from '../lib/api'
import SaldoPlano from '../components/SaldoPlano'
import { enviarFoto, pct, type Coleta, type Deteccao } from '../lib/coletas'

interface Resultado {
  identificada: boolean
  especie: string | null
  confianca: number | null
  mensagem: string | null
  deteccoes: Deteccao[]
  imagem_anotada?: string
}

interface Item {
  id: number
  arquivo: File
  previa: string
  situacao: 'aguardando' | 'identificando' | 'pronta' | 'erro'
  resultado?: Resultado
  erro?: string
}

const ACEITOS = ['image/jpeg', 'image/png', 'image/webp']
const MAX_FOTOS = 100
const SIMULTANEAS = 2 // o detector processa uma por vez; 2 mantém a fila andando
let proximoId = 1

async function identificar(arquivo: File): Promise<Resultado> {
  const form = new FormData()
  form.append('arquivo', arquivo)
  const enviar = (token: string | null) =>
    fetch(`${API_URL}/v1/identificar`, {
      method: 'POST',
      credentials: 'include',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    })
  let r: Response
  try {
    r = await enviar(obterToken())
    if (r.status === 401) {
      const sessao = await renovarSessao()
      if (sessao) r = await enviar(sessao.access_token)
    }
  } catch {
    throw new ErroApi(0, 'Sem conexão com o servidor.')
  }
  const corpo = await r.json().catch(() => null)
  if (!r.ok) throw new ErroApi(r.status, corpo?.detail ?? 'Não foi possível identificar.')
  return corpo
}

function Resumo({ itens }: { itens: Item[] }) {
  const prontas = itens.filter((i) => i.situacao === 'pronta')
  const contagem = new Map<string, number>()
  let naoIdentificadas = 0
  for (const i of prontas) {
    if (i.resultado?.identificada && i.resultado.especie) {
      contagem.set(i.resultado.especie, (contagem.get(i.resultado.especie) ?? 0) + 1)
    } else naoIdentificadas++
  }
  const identificadas = prontas.length - naoIdentificadas
  if (!prontas.length) return null
  const linhas = [...contagem.entries()].sort((a, b) => b[1] - a[1])

  return (
    <section className="rounded-2xl border border-tinta-100 bg-white p-5 shadow-sm">
      <h2 className="font-bold text-tinta-800">Resumo</h2>
      <p className="text-xs text-tinta-500">
        Porcentagens calculadas sobre as {identificadas} foto(s) identificada(s).
        {naoIdentificadas > 0 && ` ${naoIdentificadas} não identificada(s) ficam de fora.`}
      </p>
      <ul className="mt-4 space-y-3">
        {linhas.map(([especie, n]) => (
          <li key={especie}>
            <div className="flex justify-between text-sm">
              <span className="font-semibold italic text-tinta-800">{especie}</span>
              <span className="text-tinta-500">
                {n} · {Math.round((n / identificadas) * 100)}%
              </span>
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-tinta-50">
              <div className="h-full rounded-full bg-mel-500" style={{ width: `${(n / identificadas) * 100}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function Identificar() {
  const navegar = useNavigate()
  const cliente = useQueryClient()
  const entrada = useRef<HTMLInputElement>(null)
  const [itens, setItens] = useState<Item[]>([])
  const [arrastando, setArrastando] = useState(false)
  const [aberta, setAberta] = useState<number | null>(null)
  const [aviso, setAviso] = useState('')
  const [salvando, setSalvando] = useState<{ feitas: number; total: number } | null>(null)
  const [erroSalvar, setErroSalvar] = useState('')

  // Libera a memória das prévias ao sair da página
  const itensRef = useRef(itens)
  itensRef.current = itens
  useEffect(() => () => itensRef.current.forEach((i) => URL.revokeObjectURL(i.previa)), [])

  const atualizar = (id: number, dados: Partial<Item>) =>
    setItens((lista) => lista.map((i) => (i.id === id ? { ...i, ...dados } : i)))

  async function processar(novos: Item[]) {
    const fila = [...novos]
    const trabalhador = async () => {
      for (let item = fila.shift(); item; item = fila.shift()) {
        atualizar(item.id, { situacao: 'identificando' })
        try {
          atualizar(item.id, { situacao: 'pronta', resultado: await identificar(item.arquivo) })
        } catch (e) {
          atualizar(item.id, { situacao: 'erro', erro: mensagemErro(e) })
        }
      }
    }
    await Promise.all(Array.from({ length: SIMULTANEAS }, trabalhador))
    cliente.invalidateQueries({ queryKey: ['meu-plano'] })
  }

  function adicionar(arquivos: FileList | null) {
    if (!arquivos?.length) return
    setAviso('')
    const validos = Array.from(arquivos).filter((a) => ACEITOS.includes(a.type))
    const ignorados = arquivos.length - validos.length
    const espaco = MAX_FOTOS - itens.length
    const escolhidos = validos.slice(0, Math.max(espaco, 0))
    const avisos = []
    if (ignorados) avisos.push(`${ignorados} arquivo(s) ignorado(s): envie JPEG, PNG ou WEBP.`)
    if (validos.length > escolhidos.length)
      avisos.push(`Limite de ${MAX_FOTOS} fotos por vez. Para mais fotos, use as coletas.`)
    setAviso(avisos.join(' '))

    const novos: Item[] = escolhidos.map((arquivo) => ({
      id: proximoId++,
      arquivo,
      previa: URL.createObjectURL(arquivo),
      situacao: 'aguardando',
    }))
    setItens((lista) => [...lista, ...novos])
    processar(novos)
  }

  function limpar() {
    itens.forEach((i) => URL.revokeObjectURL(i.previa))
    setItens([])
    setAviso('')
  }

  async function salvarEmColeta() {
    setErroSalvar('')
    const arquivos = itens.map((i) => i.arquivo)
    setSalvando({ feitas: 0, total: arquivos.length })
    try {
      const agora = new Date()
      const coleta = await api<Coleta>('/v1/coletas', {
        method: 'POST',
        body: {
          nome: `Identificação rápida – ${agora.toLocaleDateString('pt-BR')} ${agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`,
        },
      })
      let feitas = 0
      for (const arquivo of arquivos) {
        await enviarFoto(coleta.id, arquivo, () => {})
        setSalvando({ feitas: ++feitas, total: arquivos.length })
      }
      cliente.invalidateQueries({ queryKey: ['coletas'] })
      navegar(`/coletas/${coleta.id}`)
    } catch (e) {
      setErroSalvar(mensagemErro(e))
      setSalvando(null)
    }
  }

  function soltar(e: DragEvent) {
    e.preventDefault()
    setArrastando(false)
    adicionar(e.dataTransfer.files)
  }

  const pendentes = itens.filter((i) => i.situacao === 'aguardando' || i.situacao === 'identificando').length
  const prontas = itens.length - pendentes
  const itemAberto = itens.find((i) => i.id === aberta)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-tinta-900">Identificação rápida</h1>
        <p className="mt-1 max-w-3xl text-sm text-tinta-500">
          Envie uma ou várias fotos de asas e veja as espécies na hora, sem criar coleta. As fotos não ficam
          guardadas, mas no final você pode salvar tudo numa nova coleta. Para registrar local, armadilha e isca,
          use as <Link to="/coletas" className="font-semibold underline">coletas</Link>. Cada foto conta no limite do
          plano uma vez só, mesmo se você salvar depois.
        </p>
        <SaldoPlano className="mt-2" />
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setArrastando(true)
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={soltar}
        onClick={() => entrada.current?.click()}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && entrada.current?.click()}
        role="button"
        tabIndex={0}
        className={`cursor-pointer rounded-2xl border-2 border-dashed px-6 py-8 text-center transition ${
          arrastando ? 'border-mel-500 bg-mel-50' : 'border-tinta-100 bg-white hover:border-mel-400'
        }`}
      >
        <p className="font-semibold text-tinta-800">Arraste as fotos para cá</p>
        <p className="mt-1 text-sm text-tinta-500">ou toque para escolher · até {MAX_FOTOS} fotos · JPEG, PNG ou WEBP</p>
        <input
          ref={entrada}
          type="file"
          accept={ACEITOS.join(',')}
          multiple
          className="hidden"
          onChange={(e) => {
            adicionar(e.target.files)
            e.target.value = ''
          }}
        />
      </div>

      {aviso && <Alerta tipo="info">{aviso}</Alerta>}

      {itens.length > 0 && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="font-semibold text-tinta-800">
              {pendentes > 0 ? `Identificando… ${prontas} de ${itens.length}` : `${itens.length} foto(s) identificada(s)`}
            </p>
            <div className="flex flex-wrap gap-2">
              <Botao
                variante="destaque"
                disabled={pendentes > 0 || !!salvando}
                carregando={!!salvando}
                onClick={salvarEmColeta}
              >
                {salvando ? `Salvando ${salvando.feitas} de ${salvando.total}…` : 'Salvar numa nova coleta'}
              </Botao>
              <Botao variante="secundario" disabled={pendentes > 0 || !!salvando} onClick={limpar}>
                Limpar
              </Botao>
            </div>
          </div>
          {pendentes > 0 && (
            <div className="h-2 overflow-hidden rounded-full bg-tinta-50" role="progressbar" aria-valuenow={prontas} aria-valuemax={itens.length}>
              <div className="h-full bg-tinta-500 transition-all" style={{ width: `${(prontas / itens.length) * 100}%` }} />
            </div>
          )}
          {erroSalvar && <Alerta>{erroSalvar}</Alerta>}

          <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {itens.map((i) => (
                <li key={i.id}>
                  <button
                    onClick={() => i.situacao === 'pronta' && setAberta(i.id)}
                    className="block w-full overflow-hidden rounded-xl border border-tinta-100 bg-white text-left shadow-sm transition hover:border-mel-400"
                  >
                    <div className="aspect-[4/3] bg-tinta-50">
                      <img src={i.previa} alt="" className="h-full w-full object-cover" />
                    </div>
                    <div className="space-y-1 p-2.5 text-sm">
                      {i.situacao === 'pronta' && i.resultado?.identificada && (
                        <>
                          <p className="truncate font-semibold italic text-tinta-800">{i.resultado.especie}</p>
                          <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                            {pct(i.resultado.confianca)}
                          </span>
                        </>
                      )}
                      {i.situacao === 'pronta' && !i.resultado?.identificada && (
                        <span className="rounded-full bg-tinta-100 px-2 py-0.5 text-xs font-semibold text-tinta-700">Não identificada</span>
                      )}
                      {(i.situacao === 'aguardando' || i.situacao === 'identificando') && (
                        <span className="rounded-full bg-mel-100 px-2 py-0.5 text-xs font-semibold text-mel-700">
                          {i.situacao === 'aguardando' ? 'Na fila' : 'Identificando…'}
                        </span>
                      )}
                      {i.situacao === 'erro' && <p className="text-xs text-red-700">{i.erro}</p>}
                      <p className="truncate text-xs text-tinta-300">{i.arquivo.name}</p>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
            <div className="space-y-4">
              <Resumo itens={itens} />
              <p className="text-xs text-tinta-300">
                A identificação é automática e pode conter erros. Ela não substitui a análise de um especialista.
              </p>
            </div>
          </div>
        </>
      )}

      {itemAberto?.resultado && (
        <div className="fixed inset-0 z-[1000] flex items-start justify-center overflow-y-auto bg-tinta-900/60 p-4 sm:p-8" onClick={() => setAberta(null)}>
          <div role="dialog" aria-modal="true" className="w-full max-w-3xl rounded-2xl bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex items-center justify-between gap-4">
              <h2 className="truncate font-bold text-tinta-800">{itemAberto.arquivo.name}</h2>
              <button onClick={() => setAberta(null)} className="rounded-lg px-2 py-1 text-tinta-500 hover:bg-tinta-50" aria-label="Fechar">
                ✕
              </button>
            </div>
            <img
              src={itemAberto.resultado.imagem_anotada ? `data:image/jpeg;base64,${itemAberto.resultado.imagem_anotada}` : itemAberto.previa}
              alt="Foto com as caixas detectadas"
              className="w-full rounded-lg"
            />
            <div className="mt-4">
              {itemAberto.resultado.identificada ? (
                <>
                  <p className="text-xl font-bold italic text-tinta-900">{itemAberto.resultado.especie}</p>
                  <p className="text-sm text-tinta-500">Confiança do modelo: {pct(itemAberto.resultado.confianca)}</p>
                </>
              ) : (
                <Alerta tipo="info">{itemAberto.resultado.mensagem ?? 'Não foi possível identificar. Tente outra foto da asa.'}</Alerta>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
