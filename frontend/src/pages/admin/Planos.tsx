/** Administração dos planos: preço, limite de fotos e o que cada um inclui. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Alerta, Botao, Caixa, Campo, Carregando } from '../../components/ui'
import { api, mensagemErro } from '../../lib/api'
import { limiteTexto, preco, type Plano } from '../../lib/planos'

/** "29,90" → 2990; vazio → null (sob consulta) */
function paraCentavos(texto: string): number | null | 'invalido' {
  const t = texto.trim().replace(/^R\$\s*/, '').replace(/\./g, '').replace(',', '.')
  if (!t) return null
  const n = Number(t)
  return Number.isFinite(n) && n >= 0 ? Math.round(n * 100) : 'invalido'
}

const paraTexto = (centavos: number | null) => (centavos == null ? '' : (centavos / 100).toFixed(2).replace('.', ','))

type Campos = { nome: string; descricao: string; preco: string; limite: string; permite_exportacao: boolean; publico: boolean; ordem: string }

function camposDe(p?: Plano): Campos {
  return {
    nome: p?.nome ?? '',
    descricao: p?.descricao ?? '',
    preco: paraTexto(p?.preco_mensal_centavos ?? null),
    limite: p?.limite_fotos_mes != null ? String(p.limite_fotos_mes) : '',
    permite_exportacao: p?.permite_exportacao ?? true,
    publico: p?.publico ?? true,
    ordem: String(p?.ordem ?? 0),
  }
}

function corpo(c: Campos) {
  const centavos = paraCentavos(c.preco)
  if (centavos === 'invalido') throw new Error('Preço inválido. Use o formato 29,90.')
  return {
    nome: c.nome.trim(),
    descricao: c.descricao.trim() || null,
    preco_mensal_centavos: centavos,
    limite_fotos_mes: c.limite.trim() ? Number(c.limite) : null,
    permite_exportacao: c.permite_exportacao,
    publico: c.publico,
    ordem: Number(c.ordem) || 0,
  }
}

function Formulario({ inicial, aoSalvar, salvando, texto, comCodigo }: {
  inicial: Campos
  aoSalvar: (c: Campos & { codigo?: string }) => void
  salvando: boolean
  texto: string
  comCodigo?: boolean
}) {
  const [c, setC] = useState(inicial)
  const [codigo, setCodigo] = useState('')
  const mudar = (k: keyof Campos) => (e: { target: { value: string } }) => setC({ ...c, [k]: e.target.value })
  const enviar = (e: FormEvent) => {
    e.preventDefault()
    aoSalvar({ ...c, ...(comCodigo ? { codigo } : {}) })
  }
  return (
    <form onSubmit={enviar} className="grid gap-3 sm:grid-cols-6">
      {comCodigo && (
        <Campo rotulo="Código" className="sm:col-span-2" value={codigo} onChange={(e) => setCodigo(e.target.value.toLowerCase())} required pattern="[a-z0-9_-]{2,40}" dica="Letras minúsculas, sem espaço. Não muda depois." />
      )}
      <Campo rotulo="Nome" className={comCodigo ? 'sm:col-span-4' : 'sm:col-span-2'} value={c.nome} onChange={mudar('nome')} required minLength={2} maxLength={80} />
      <Campo rotulo="Preço por mês (R$)" className="sm:col-span-2" inputMode="decimal" placeholder="Vazio = sob consulta" value={c.preco} onChange={mudar('preco')} />
      <Campo rotulo="Fotos por mês" className="sm:col-span-2" type="number" min={1} placeholder="Vazio = sem limite" value={c.limite} onChange={mudar('limite')} />
      <Campo rotulo="Descrição" className="sm:col-span-4" value={c.descricao} onChange={mudar('descricao')} maxLength={1000} />
      <Campo rotulo="Ordem" className="sm:col-span-2" type="number" value={c.ordem} onChange={mudar('ordem')} dica="Posição na página de planos" />
      <div className="flex flex-wrap items-center gap-6 sm:col-span-6">
        <Caixa checked={c.permite_exportacao} onChange={(e) => setC({ ...c, permite_exportacao: e.target.checked })}>Inclui exportação ZIP</Caixa>
        <Caixa checked={c.publico} onChange={(e) => setC({ ...c, publico: e.target.checked })}>Aparece no site e pode ser pedido</Caixa>
        <Botao type="submit" carregando={salvando} className="ml-auto">{texto}</Botao>
      </div>
    </form>
  )
}

export default function AdminPlanos() {
  const cliente = useQueryClient()
  const planos = useQuery({ queryKey: ['admin-planos'], queryFn: () => api<Plano[]>('/v1/admin/planos') })
  const [aberto, setAberto] = useState<number | 'novo' | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  const salvar = useMutation({
    mutationFn: ({ id, c }: { id: number | 'novo'; c: Campos & { codigo?: string } }) => {
      const dados = corpo(c)
      return id === 'novo'
        ? api<Plano>('/v1/admin/planos', { method: 'POST', body: { ...dados, codigo: c.codigo } })
        : api<Plano>(`/v1/admin/planos/${id}`, { method: 'PATCH', body: dados })
    },
    onSuccess: (p) => {
      cliente.invalidateQueries({ queryKey: ['admin-planos'] })
      cliente.invalidateQueries({ queryKey: ['planos'] })
      cliente.invalidateQueries({ queryKey: ['meu-plano'] })
      setAberto(null)
      setAviso(`Plano ${p.nome} salvo.`)
    },
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-tinta-900">Planos</h1>
          <p className="mt-1 max-w-3xl text-sm text-tinta-500">
            Mudanças valem na hora para todos os assinantes do plano. O limite conta as fotos das coletas e as da
            identificação rápida em cada mês. Para ativar o plano de alguém, use a aba Usuários.
          </p>
        </div>
        <Botao variante="secundario" onClick={() => setAberto('novo')}>Novo plano</Botao>
      </div>

      {aviso && <Alerta tipo="sucesso">{aviso}</Alerta>}
      {(salvar.error || planos.error) && (
        <Alerta>{salvar.error instanceof Error && !('status' in salvar.error) ? salvar.error.message : mensagemErro(salvar.error ?? planos.error)}</Alerta>
      )}
      {planos.isLoading && <Carregando />}

      {aberto === 'novo' && (
        <section className="rounded-2xl border border-mel-200 bg-white p-5">
          <h2 className="mb-3 font-bold text-tinta-800">Novo plano</h2>
          <Formulario inicial={camposDe()} comCodigo texto="Criar plano" salvando={salvar.isPending} aoSalvar={(c) => salvar.mutate({ id: 'novo', c })} />
        </section>
      )}

      <ul className="space-y-3">
        {planos.data?.map((p) => (
          <li key={p.id} className="rounded-2xl border border-tinta-100 bg-white p-5">
            {aberto === p.id ? (
              <Formulario inicial={camposDe(p)} texto="Salvar" salvando={salvar.isPending} aoSalvar={(c) => salvar.mutate({ id: p.id, c })} />
            ) : (
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="flex flex-wrap items-center gap-2">
                    <span className="text-lg font-bold text-tinta-900">{p.nome}</span>
                    <code className="rounded bg-tinta-50 px-1.5 text-xs text-tinta-500">{p.codigo}</code>
                    {!p.publico && <span className="rounded-full bg-tinta-50 px-2 py-0.5 text-xs font-semibold text-tinta-500">Oculto</span>}
                  </p>
                  {p.descricao && <p className="mt-1 text-sm text-tinta-700">{p.descricao}</p>}
                  <p className="mt-2 text-sm text-tinta-800">
                    {preco(p.preco_mensal_centavos) ? `${preco(p.preco_mensal_centavos)} por mês` : 'Valor sob consulta'};{' '}
                    {limiteTexto(p.limite_fotos_mes).toLowerCase()}; {p.permite_exportacao ? 'com exportação' : 'sem exportação'}
                  </p>
                </div>
                <Botao variante="secundario" className="!py-1.5" onClick={() => setAberto(p.id)}>Editar</Botao>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
