/** Área de envio de fotos: arrastar e soltar, várias de uma vez, com progresso. */
import { useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { mensagemErro } from '../../lib/api'
import SaldoPlano from '../../components/SaldoPlano'
import { enviarFoto } from '../../lib/coletas'
import { useMeuPlano } from '../../lib/planos'

type Situacao = 'aguardando' | 'enviando' | 'enviada' | 'recusada'

interface Item {
  id: number
  arquivo: File
  situacao: Situacao
  progresso: number
  motivo?: string
}

const ACEITOS = ['image/jpeg', 'image/png', 'image/webp']
const SIMULTANEOS = 3 // quantas fotos sobem ao mesmo tempo

let proximoId = 1

export default function Envio({ coletaId }: { coletaId: string }) {
  const cliente = useQueryClient()
  const entrada = useRef<HTMLInputElement>(null)
  const [itens, setItens] = useState<Item[]>([])
  const [arrastando, setArrastando] = useState(false)
  const [ativo, setAtivo] = useState(false)
  // Sem plano válido ou sem saldo: a área de envio fica desligada (o aviso explica o motivo)
  const plano = useMeuPlano()
  const bloqueado = !!plano.data && !plano.data.pode_enviar

  const atualizar = (id: number, dados: Partial<Item>) =>
    setItens((lista) => lista.map((i) => (i.id === id ? { ...i, ...dados } : i)))

  async function enviarTodos(novos: Item[]) {
    setAtivo(true)
    const fila = [...novos]
    const trabalhador = async () => {
      for (let item = fila.shift(); item; item = fila.shift()) {
        atualizar(item.id, { situacao: 'enviando' })
        try {
          const r = await enviarFoto(coletaId, item.arquivo, (p) => atualizar(item!.id, { progresso: p }))
          if (r.rejeitadas.length) atualizar(item.id, { situacao: 'recusada', motivo: r.rejeitadas[0].motivo })
          else atualizar(item.id, { situacao: 'enviada', progresso: 1 })
        } catch (e) {
          atualizar(item.id, { situacao: 'recusada', motivo: mensagemErro(e) })
        }
        // Atualiza a contagem e a grade enquanto envia
        cliente.invalidateQueries({ queryKey: ['progresso', coletaId] })
      }
    }
    await Promise.all(Array.from({ length: SIMULTANEOS }, trabalhador))
    setAtivo(false)
    cliente.invalidateQueries({ queryKey: ['meu-plano'] })
    cliente.invalidateQueries({ queryKey: ['fotos', coletaId] })
    cliente.invalidateQueries({ queryKey: ['coletas'] })
  }

  function adicionar(arquivos: FileList | null) {
    if (!arquivos?.length || bloqueado) return
    const novos: Item[] = Array.from(arquivos).map((arquivo) => ({
      id: proximoId++,
      arquivo,
      situacao: 'aguardando',
      progresso: 0,
      ...(ACEITOS.includes(arquivo.type) ? {} : { situacao: 'recusada' as const, motivo: 'Formato não aceito. Envie JPEG, PNG ou WEBP.' }),
    }))
    setItens((lista) => [...novos, ...lista.filter((i) => i.situacao !== 'enviada')])
    enviarTodos(novos.filter((n) => n.situacao === 'aguardando'))
  }

  function soltar(e: DragEvent) {
    e.preventDefault()
    setArrastando(false)
    adicionar(e.dataTransfer.files)
  }

  const enviadas = itens.filter((i) => i.situacao === 'enviada').length
  const recusadas = itens.filter((i) => i.situacao === 'recusada')
  const emAndamento = itens.filter((i) => i.situacao === 'enviando' || i.situacao === 'aguardando')
  const progressoTotal = itens.length
    ? itens.reduce((s, i) => s + (i.situacao === 'recusada' ? 1 : i.progresso), 0) / itens.length
    : 0

  return (
    <section className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setArrastando(true)
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={soltar}
        onClick={() => !bloqueado && entrada.current?.click()}
        onKeyDown={(e) => !bloqueado && (e.key === 'Enter' || e.key === ' ') && entrada.current?.click()}
        role="button"
        tabIndex={bloqueado ? -1 : 0}
        aria-disabled={bloqueado}
        className={`rounded-2xl border-2 border-dashed px-6 py-10 text-center transition ${
          bloqueado
            ? 'cursor-not-allowed border-tinta-100 bg-tinta-50 opacity-60'
            : arrastando
              ? 'cursor-pointer border-mel-500 bg-mel-50'
              : 'cursor-pointer border-tinta-100 bg-white hover:border-mel-400'
        }`}
      >
        <svg viewBox="0 0 24 24" className="mx-auto h-10 w-10 text-mel-500" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
          <path d="M12 16V4m0 0-4 4m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <p className="mt-3 font-semibold text-tinta-800">Arraste as fotos das asas para cá</p>
        <p className="mt-1 text-sm text-tinta-500">ou toque para escolher · JPEG, PNG ou WEBP · várias de uma vez</p>
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

      <SaldoPlano />

      {itens.length > 0 && (
        <div className="rounded-2xl border border-tinta-100 bg-white p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="font-semibold text-tinta-800">
              {ativo ? `Enviando… ${enviadas} de ${itens.length - recusadas.length}` : `${enviadas} foto(s) enviada(s)`}
            </span>
            {!ativo && (
              <button className="text-xs text-tinta-500 hover:text-tinta-800" onClick={() => setItens([])}>
                Limpar
              </button>
            )}
          </div>
          {ativo && (
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-tinta-50" role="progressbar" aria-valuenow={Math.round(progressoTotal * 100)}>
              <div className="h-full bg-mel-500 transition-all" style={{ width: `${progressoTotal * 100}%` }} />
            </div>
          )}
          {emAndamento.length > 0 && (
            <p className="mt-2 text-xs text-tinta-500">Não feche esta página até o envio terminar.</p>
          )}
          {recusadas.length > 0 && (
            <ul className="mt-3 space-y-1 text-sm">
              {recusadas.map((i) => (
                <li key={i.id} className="text-red-700">
                  <span className="font-semibold">{i.arquivo.name}:</span> {i.motivo}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}
