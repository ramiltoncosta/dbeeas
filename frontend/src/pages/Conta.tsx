/** Telas de entrar, cadastrar, esqueci a senha e redefinir senha. */
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Alerta, Botao, Caixa, Campo, Cartao, Selecao } from '../components/ui'
import { api, ErroApi } from '../lib/api'
import { useAuth, type DadosCadastro } from '../lib/auth'

const msg = (e: unknown) => (e instanceof ErroApi ? e.message : 'Algo deu errado. Tente novamente.')

function Titulo({ titulo, sub }: { titulo: string; sub?: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-bold text-tinta-900">{titulo}</h1>
      {sub && <p className="mt-1 text-sm text-tinta-500">{sub}</p>}
    </div>
  )
}

export function Entrar() {
  const { entrar } = useAuth()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      await entrar(email, senha) // o redirecionamento acontece em <SomenteVisitante>
    } catch (err) {
      setErro(msg(err))
      setEnviando(false)
    }
  }

  return (
    <Cartao>
      <Titulo titulo="Entrar" sub="Acesse sua conta do DBeeAS." />
      <form onSubmit={enviar} className="space-y-4">
        {erro && <Alerta>{erro}</Alerta>}
        <Campo rotulo="E-mail" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Campo rotulo="Senha" type="password" autoComplete="current-password" required value={senha} onChange={(e) => setSenha(e.target.value)} />
        <div className="text-right">
          <Link to="/esqueci-senha" className="text-sm font-medium text-tinta-500 hover:text-tinta-800">
            Esqueci minha senha
          </Link>
        </div>
        <Botao type="submit" carregando={enviando} className="w-full">
          Entrar
        </Botao>
      </form>
      <p className="mt-6 text-center text-sm text-tinta-500">
        Ainda não tem conta?{' '}
        <Link to="/cadastrar" className="font-semibold text-mel-700 hover:text-mel-600">
          Criar conta
        </Link>
      </p>
    </Cartao>
  )
}

export function Cadastrar() {
  const { cadastrar } = useAuth()
  const [dados, setDados] = useState<DadosCadastro>({
    nome: '',
    email: '',
    senha: '',
    perfil: 'pesquisador',
    instituicao: '',
    aceite_termos: false,
    consentimento_uso_fotos: false,
  })
  const [confirmacao, setConfirmacao] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  const mudar = <K extends keyof DadosCadastro>(campo: K, valor: DadosCadastro[K]) =>
    setDados((d) => ({ ...d, [campo]: valor }))

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setErro('')
    if (dados.senha !== confirmacao) return setErro('As senhas não conferem.')
    if (!dados.aceite_termos) return setErro('É preciso aceitar os termos de uso e a política de privacidade.')
    setEnviando(true)
    try {
      await cadastrar(dados)
    } catch (err) {
      setErro(msg(err))
      setEnviando(false)
    }
  }

  return (
    <Cartao>
      <Titulo titulo="Criar conta" sub="Identifique abelhas pela asa e organize suas coletas." />
      <form onSubmit={enviar} className="space-y-4">
        {erro && <Alerta>{erro}</Alerta>}
        <Campo rotulo="Nome completo" autoComplete="name" required minLength={2} value={dados.nome} onChange={(e) => mudar('nome', e.target.value)} />
        <Campo rotulo="E-mail" type="email" autoComplete="email" required value={dados.email} onChange={(e) => mudar('email', e.target.value)} />
        <Selecao rotulo="Você é" value={dados.perfil} onChange={(e) => mudar('perfil', e.target.value as DadosCadastro['perfil'])}>
          <option value="pesquisador">Pesquisador(a)</option>
          <option value="orgao_publico">Órgão público</option>
          <option value="estudante">Estudante</option>
        </Selecao>
        <Campo rotulo="Instituição (opcional)" placeholder="Ex.: UFMT, Embrapa, SEMA-MT" value={dados.instituicao} onChange={(e) => mudar('instituicao', e.target.value)} />
        <Campo rotulo="Senha" type="password" autoComplete="new-password" required minLength={8} dica="Mínimo de 8 caracteres." value={dados.senha} onChange={(e) => mudar('senha', e.target.value)} />
        <Campo rotulo="Repita a senha" type="password" autoComplete="new-password" required value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} />
        <div className="space-y-3 rounded-lg bg-mel-50 p-4">
          <Caixa checked={dados.aceite_termos} onChange={(e) => mudar('aceite_termos', e.target.checked)}>
            Li e aceito os{' '}
            <Link to="/termos" target="_blank" className="font-semibold underline">termos de uso</Link> e a{' '}
            <Link to="/privacidade" target="_blank" className="font-semibold underline">política de privacidade</Link>.
          </Caixa>
          <Caixa checked={dados.consentimento_uso_fotos} onChange={(e) => mudar('consentimento_uso_fotos', e.target.checked)}>
            Autorizo o uso das minhas fotos para melhorar o modelo de identificação (opcional, posso mudar depois).
          </Caixa>
        </div>
        <Botao type="submit" variante="destaque" carregando={enviando} className="w-full">
          Criar conta
        </Botao>
      </form>
      <p className="mt-6 text-center text-sm text-tinta-500">
        Já tem conta?{' '}
        <Link to="/entrar" className="font-semibold text-mel-700 hover:text-mel-600">Entrar</Link>
      </p>
    </Cartao>
  )
}

export function EsqueciSenha() {
  const [email, setEmail] = useState('')
  const [resposta, setResposta] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      const r = await api<{ mensagem: string }>('/v1/auth/esqueci-senha', { method: 'POST', body: { email }, semRenovar: true })
      setResposta(r.mensagem)
    } catch (err) {
      setErro(msg(err))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Cartao>
      <Titulo titulo="Esqueci minha senha" sub="Enviaremos um link para você criar uma nova senha." />
      {resposta ? (
        <Alerta tipo="sucesso">{resposta}</Alerta>
      ) : (
        <form onSubmit={enviar} className="space-y-4">
          {erro && <Alerta>{erro}</Alerta>}
          <Campo rotulo="E-mail da conta" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <Botao type="submit" carregando={enviando} className="w-full">Enviar link</Botao>
        </form>
      )}
      <p className="mt-6 text-center text-sm">
        <Link to="/entrar" className="font-semibold text-tinta-500 hover:text-tinta-800">Voltar para entrar</Link>
      </p>
    </Cartao>
  )
}

export function RedefinirSenha() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const [senha, setSenha] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [erro, setErro] = useState('')
  const [pronto, setPronto] = useState(false)
  const [enviando, setEnviando] = useState(false)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setErro('')
    if (senha !== confirmacao) return setErro('As senhas não conferem.')
    setEnviando(true)
    try {
      await api('/v1/auth/redefinir-senha', { method: 'POST', body: { token, nova_senha: senha }, semRenovar: true })
      setPronto(true)
    } catch (err) {
      setErro(msg(err))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Cartao>
      <Titulo titulo="Criar nova senha" />
      {!token ? (
        <Alerta>Link inválido. Peça um novo link em “Esqueci minha senha”.</Alerta>
      ) : pronto ? (
        <div className="space-y-4">
          <Alerta tipo="sucesso">Senha alterada com sucesso.</Alerta>
          <Link to="/entrar" className="block rounded-lg bg-tinta-700 px-4 py-2.5 text-center text-sm font-semibold text-white hover:bg-tinta-800">
            Entrar com a nova senha
          </Link>
        </div>
      ) : (
        <form onSubmit={enviar} className="space-y-4">
          {erro && <Alerta>{erro}</Alerta>}
          <Campo rotulo="Nova senha" type="password" autoComplete="new-password" required minLength={8} dica="Mínimo de 8 caracteres." value={senha} onChange={(e) => setSenha(e.target.value)} />
          <Campo rotulo="Repita a nova senha" type="password" autoComplete="new-password" required value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} />
          <Botao type="submit" carregando={enviando} className="w-full">Salvar nova senha</Botao>
        </form>
      )}
    </Cartao>
  )
}
