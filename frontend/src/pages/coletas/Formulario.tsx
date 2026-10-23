/** Criar e editar coleta. */
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import SeletorLocal from '../../components/SeletorLocal'
import { Alerta, Botao, Caixa, Campo, Carregando, Cartao, Selecao } from '../../components/ui'
import { api, mensagemErro } from '../../lib/api'
import { BIOMAS, UFS, type CamposColeta, type Coleta } from '../../lib/coletas'

const VAZIO: CamposColeta = {
  nome: '',
  descricao: null,
  data_coleta: null,
  municipio: null,
  uf: null,
  coletor: null,
  tipo_armadilha: null,
  isca_atrativa: null,
  bioma: null,
  observacoes: null,
  local: null,
  publica_no_mapa: true,
}

const CAMPOS = Object.keys(VAZIO) as (keyof CamposColeta)[]

function AreaTexto({ rotulo, valor, aoMudar }: { rotulo: string; valor: string | null; aoMudar: (v: string) => void }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-tinta-800">{rotulo}</span>
      <textarea
        rows={3}
        className="w-full rounded-lg border border-tinta-100 bg-white px-3 py-2.5 text-base shadow-sm focus:border-mel-500 focus:outline-none focus:ring-2 focus:ring-mel-200"
        value={valor ?? ''}
        onChange={(e) => aoMudar(e.target.value)}
      />
    </label>
  )
}

function Form({ inicial, coletaId }: { inicial: CamposColeta; coletaId?: string }) {
  const navegar = useNavigate()
  const cliente = useQueryClient()
  const [dados, setDados] = useState<CamposColeta>(inicial)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  const mudar = <K extends keyof CamposColeta>(campo: K, valor: CamposColeta[K]) => setDados((d) => ({ ...d, [campo]: valor }))
  const texto = (campo: keyof CamposColeta) => (e: { target: { value: string } }) =>
    mudar(campo, (e.target.value || null) as never)

  async function salvar(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setEnviando(true)
    const corpo = Object.fromEntries(CAMPOS.map((c) => [c, dados[c]]))
    try {
      const coleta = coletaId
        ? await api<Coleta>(`/v1/coletas/${coletaId}`, { method: 'PATCH', body: corpo })
        : await api<Coleta>('/v1/coletas', { method: 'POST', body: corpo })
      await cliente.invalidateQueries({ queryKey: ['coletas'] })
      cliente.setQueryData(['coleta', coleta.id], coleta)
      navegar(`/coletas/${coleta.id}`)
    } catch (err) {
      setErro(mensagemErro(err))
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={salvar} className="space-y-6">
      {erro && <Alerta>{erro}</Alerta>}
      <Cartao className="space-y-4">
        <h2 className="text-lg font-bold text-tinta-800">Identificação da coleta</h2>
        <Campo rotulo="Nome da coleta" required maxLength={200} placeholder="Ex.: Fazenda Boa Vista – outubro" value={dados.nome} onChange={(e) => mudar('nome', e.target.value)} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo rotulo="Data da coleta" type="date" max={new Date().toISOString().slice(0, 10)} value={dados.data_coleta ?? ''} onChange={texto('data_coleta')} />
          <Campo rotulo="Coletor(a)" value={dados.coletor ?? ''} onChange={texto('coletor')} />
        </div>
        <AreaTexto rotulo="Descrição" valor={dados.descricao} aoMudar={(v) => mudar('descricao', v || null)} />
      </Cartao>

      <Cartao className="space-y-4">
        <h2 className="text-lg font-bold text-tinta-800">Local</h2>
        <div className="grid gap-4 sm:grid-cols-[1fr_120px_1fr]">
          <Campo rotulo="Município" value={dados.municipio ?? ''} onChange={texto('municipio')} />
          <Selecao rotulo="UF" value={dados.uf ?? ''} onChange={texto('uf')}>
            <option value="">—</option>
            {UFS.map((uf) => <option key={uf}>{uf}</option>)}
          </Selecao>
          <Selecao rotulo="Bioma" value={dados.bioma ?? ''} onChange={texto('bioma')}>
            <option value="">—</option>
            {Object.entries(BIOMAS).map(([v, n]) => <option key={v} value={v}>{n}</option>)}
          </Selecao>
        </div>
        <div>
          <p className="mb-1 text-sm font-medium text-tinta-800">Ponto da coleta no mapa</p>
          <p className="mb-2 text-xs text-tinta-500">
            Fotos sem localização própria (sem GPS) usam este ponto.
          </p>
          <SeletorLocal valor={dados.local} aoMudar={(p) => mudar('local', p)} />
        </div>
        <Caixa checked={dados.publica_no_mapa} onChange={(e) => mudar('publica_no_mapa', e.target.checked)}>
          Mostrar as ocorrências desta coleta no mapa geral da plataforma
          <span className="block text-xs text-tinta-500">
            Outras pessoas veem só a espécie, a data e o ponto (aproximado, no caso de espécies sensíveis), sem fotos
            nem o nome da coleta. Desmarque se o local for sigiloso, como uma propriedade particular.
          </span>
        </Caixa>
      </Cartao>

      <Cartao className="space-y-4">
        <h2 className="text-lg font-bold text-tinta-800">Método de coleta</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo rotulo="Tipo de armadilha" placeholder="Ex.: garrafa PET, rede entomológica" value={dados.tipo_armadilha ?? ''} onChange={texto('tipo_armadilha')} />
          <Campo rotulo="Isca atrativa" placeholder="Ex.: eucaliptol, salicilato de metila" value={dados.isca_atrativa ?? ''} onChange={texto('isca_atrativa')} />
        </div>
        <AreaTexto rotulo="Observações" valor={dados.observacoes} aoMudar={(v) => mudar('observacoes', v || null)} />
      </Cartao>

      <div className="flex flex-wrap gap-3">
        <Botao type="submit" carregando={enviando}>{coletaId ? 'Salvar alterações' : 'Criar coleta'}</Botao>
        <Link to={coletaId ? `/coletas/${coletaId}` : '/coletas'} className="rounded-lg border border-tinta-100 bg-white px-4 py-2.5 text-sm font-semibold text-tinta-800 hover:bg-tinta-50">
          Cancelar
        </Link>
      </div>
    </form>
  )
}

export default function FormularioColeta() {
  const { id } = useParams()
  const consulta = useQuery({
    queryKey: ['coleta', id],
    queryFn: () => api<Coleta>(`/v1/coletas/${id}`),
    enabled: !!id,
  })

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold text-tinta-900">{id ? 'Editar coleta' : 'Nova coleta'}</h1>
      {!id && <Form inicial={VAZIO} />}
      {id && consulta.isLoading && <Carregando />}
      {id && consulta.error && <Alerta>{mensagemErro(consulta.error)}</Alerta>}
      {id && consulta.data && (
        <Form key={consulta.data.id} coletaId={id} inicial={Object.fromEntries(CAMPOS.map((c) => [c, consulta.data[c]])) as unknown as CamposColeta} />
      )}
    </div>
  )
}
