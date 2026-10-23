import { useState } from 'react'
import type { FormEvent } from 'react'
import { Alerta, Botao, Caixa, Campo, Cartao } from '../components/ui'
import { api, baixarArquivo, ErroApi, NOMES_PERFIL, type Sessao, type Usuario } from '../lib/api'
import { useAuth } from '../lib/auth'

const msg = (e: unknown) => (e instanceof ErroApi ? e.message : 'Algo deu errado. Tente novamente.')

function DadosPessoais({ usuario }: { usuario: Usuario }) {
  const { atualizarUsuario } = useAuth()
  const [nome, setNome] = useState(usuario.nome)
  const [instituicao, setInstituicao] = useState(usuario.instituicao ?? '')
  const [consentimento, setConsentimento] = useState(usuario.consentimento_uso_fotos)
  const [aviso, setAviso] = useState<{ tipo: 'erro' | 'sucesso'; texto: string } | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function salvar(e: FormEvent) {
    e.preventDefault()
    setEnviando(true)
    setAviso(null)
    try {
      const atualizado = await api<Usuario>('/v1/eu', {
        method: 'PATCH',
        body: { nome, instituicao, consentimento_uso_fotos: consentimento },
      })
      atualizarUsuario(atualizado)
      setAviso({ tipo: 'sucesso', texto: 'Dados salvos.' })
    } catch (err) {
      setAviso({ tipo: 'erro', texto: msg(err) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Cartao>
      <h2 className="text-lg font-bold text-tinta-800">Dados pessoais</h2>
      <p className="mb-4 text-sm text-tinta-500">
        {usuario.email} · {NOMES_PERFIL[usuario.perfil]}
      </p>
      <form onSubmit={salvar} className="space-y-4">
        {aviso && <Alerta tipo={aviso.tipo}>{aviso.texto}</Alerta>}
        <Campo rotulo="Nome completo" required minLength={2} value={nome} onChange={(e) => setNome(e.target.value)} />
        <Campo rotulo="Instituição" value={instituicao} onChange={(e) => setInstituicao(e.target.value)} />
        <Caixa checked={consentimento} onChange={(e) => setConsentimento(e.target.checked)}>
          Autorizo o uso das minhas fotos para melhorar o modelo de identificação.
        </Caixa>
        <Botao type="submit" carregando={enviando}>Salvar</Botao>
      </form>
    </Cartao>
  )
}

function TrocarSenha() {
  const { aplicarSessao } = useAuth()
  const [atual, setAtual] = useState('')
  const [nova, setNova] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [aviso, setAviso] = useState<{ tipo: 'erro' | 'sucesso'; texto: string } | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function salvar(e: FormEvent) {
    e.preventDefault()
    setAviso(null)
    if (nova !== confirmacao) return setAviso({ tipo: 'erro', texto: 'As senhas não conferem.' })
    setEnviando(true)
    try {
      aplicarSessao(await api<Sessao>('/v1/eu/senha', { method: 'POST', body: { senha_atual: atual, nova_senha: nova } }))
      setAtual('')
      setNova('')
      setConfirmacao('')
      setAviso({ tipo: 'sucesso', texto: 'Senha alterada. As outras sessões abertas foram encerradas.' })
    } catch (err) {
      setAviso({ tipo: 'erro', texto: msg(err) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Cartao>
      <h2 className="mb-4 text-lg font-bold text-tinta-800">Trocar senha</h2>
      <form onSubmit={salvar} className="space-y-4">
        {aviso && <Alerta tipo={aviso.tipo}>{aviso.texto}</Alerta>}
        <Campo rotulo="Senha atual" type="password" autoComplete="current-password" required value={atual} onChange={(e) => setAtual(e.target.value)} />
        <Campo rotulo="Nova senha" type="password" autoComplete="new-password" required minLength={8} value={nova} onChange={(e) => setNova(e.target.value)} />
        <Campo rotulo="Repita a nova senha" type="password" autoComplete="new-password" required value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} />
        <Botao type="submit" carregando={enviando}>Trocar senha</Botao>
      </form>
    </Cartao>
  )
}

function MeusDados() {
  const { atualizarUsuario } = useAuth()
  const [confirmando, setConfirmando] = useState(false)
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function exportar() {
    setErro('')
    try {
      await baixarArquivo('/v1/eu/dados', 'meus-dados-dbeeas.json')
    } catch (err) {
      setErro(msg(err))
    }
  }

  async function excluir(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      await api('/v1/eu', { method: 'DELETE', body: { senha } })
      atualizarUsuario(null)
    } catch (err) {
      setErro(msg(err))
      setEnviando(false)
    }
  }

  return (
    <Cartao>
      <h2 className="text-lg font-bold text-tinta-800">Seus dados (LGPD)</h2>
      <p className="mb-4 text-sm text-tinta-500">
        Você pode baixar uma cópia de todos os dados que guardamos sobre você ou excluir sua conta.
      </p>
      {erro && <div className="mb-4"><Alerta>{erro}</Alerta></div>}
      <div className="flex flex-wrap gap-3">
        <Botao variante="secundario" onClick={exportar}>Baixar meus dados</Botao>
        {!confirmando && (
          <Botao variante="perigo" onClick={() => setConfirmando(true)}>Excluir minha conta</Botao>
        )}
      </div>
      {confirmando && (
        <form onSubmit={excluir} className="mt-5 space-y-4 rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-800">
            <strong>Atenção:</strong> a exclusão é definitiva. Todos os seus dados serão apagados e não poderão ser
            recuperados. Digite sua senha para confirmar.
          </p>
          <Campo rotulo="Sua senha" type="password" autoComplete="current-password" required value={senha} onChange={(e) => setSenha(e.target.value)} />
          <div className="flex gap-3">
            <Botao type="submit" variante="perigo" carregando={enviando}>Excluir definitivamente</Botao>
            <Botao type="button" variante="secundario" onClick={() => setConfirmando(false)}>Cancelar</Botao>
          </div>
        </form>
      )}
    </Cartao>
  )
}

export default function MinhaConta() {
  const { usuario } = useAuth()
  if (!usuario) return null
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-tinta-900">Minha conta</h1>
      <div className="grid gap-6 lg:grid-cols-2">
        <DadosPessoais usuario={usuario} />
        <TrocarSenha />
      </div>
      <MeusDados />
    </div>
  )
}
