/**
 * Página inicial pública (dbeeas.com.br): o que é, como funciona, para quem é,
 * espécies, planos e contato.
 */
import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import Asa from '../components/Asa'
import { Alerta, AreaTexto, Botao, Campo, Selecao } from '../components/ui'
import { api, mensagemErro } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { EspecieResumo } from '../lib/especies'

const largura = 'mx-auto w-full max-w-6xl px-4'

function Titulo({ children, id, claro = false }: { children: ReactNode; id?: string; claro?: boolean }) {
  return (
    <h2 id={id} className={`font-display text-3xl font-bold tracking-tight sm:text-4xl ${claro ? 'text-white' : 'text-tinta-900'}`}>
      {children}
    </h2>
  )
}

function Abertura() {
  const { usuario } = useAuth()
  return (
    <section className={`${largura} grid items-center gap-10 py-14 sm:py-20 lg:grid-cols-[1fr_1.1fr]`}>
      <div>
        <h1 className="font-display text-5xl font-extrabold leading-[1.02] tracking-tight text-tinta-900 sm:text-6xl">
          Fotografe a asa. Saiba a espécie.
        </h1>
        <p className="mt-6 max-w-xl text-lg leading-relaxed text-tinta-700">
          O DBeeAS identifica abelhas pelas nervuras da asa usando inteligência artificial. Envie as fotos da coleta de
          uma vez e receba as espécies separadas, o mapa das ocorrências e a planilha pronta para publicar.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          {usuario ? (
            <Link to="/painel" className="rounded-lg bg-tinta-700 px-5 py-3 font-semibold text-white hover:bg-tinta-800">
              Ir para o painel
            </Link>
          ) : (
            <Link to="/cadastrar" className="rounded-lg bg-mel-500 px-5 py-3 font-semibold text-tinta-900 hover:bg-mel-400">
              Criar conta
            </Link>
          )}
          <a href="#como-funciona" className="rounded-lg border border-tinta-100 bg-white px-5 py-3 font-semibold text-tinta-800 hover:bg-tinta-50">
            Como funciona
          </a>
        </div>
      </div>

      <figure>
        <div
          className="rounded-2xl border border-tinta-100 bg-white p-4 sm:p-8"
          style={{
            // Papel milimetrado, como o fundo das fotos feitas na lupa
            backgroundImage:
              'linear-gradient(rgb(31 78 95 / 0.07) 1px, transparent 1px), linear-gradient(90deg, rgb(31 78 95 / 0.07) 1px, transparent 1px)',
            backgroundSize: '16px 16px',
          }}
        >
          <Asa deteccao={{ especie: 'Euglossa cognata', confianca: 0.93 }} className="w-full" />
        </div>
        <figcaption className="mt-3 text-sm text-tinta-500">
          O modelo encontra a asa na foto, marca a região e indica a espécie com o grau de confiança.
        </figcaption>
      </figure>
    </section>
  )
}

const PASSOS = [
  ['Fotografe as asas', 'Na lupa ou no microscópio, com o celular ou a câmera. Se a foto tiver GPS, o local é lido sozinho.'],
  ['Envie a coleta inteira', 'Arraste dezenas de fotos de uma vez. Elas entram numa fila e são identificadas uma a uma.'],
  ['Confira e corrija', 'Veja as fotos agrupadas por espécie e o gráfico da coleta. Confirme ou corrija o que precisar.'],
  ['Use os dados', 'Abra o mapa das ocorrências e baixe o ZIP com as fotos por espécie e a planilha Darwin Core.'],
]

function ComoFunciona() {
  return (
    <section id="como-funciona" aria-labelledby="titulo-como" className="scroll-mt-4 bg-tinta-800 py-16 sm:py-20">
      <div className={largura}>
        <Titulo id="titulo-como" claro>Como funciona</Titulo>
        <ol className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {PASSOS.map(([titulo, texto], i) => (
            <li key={titulo} className="border-t-2 border-mel-500 pt-4">
              <span className="font-display text-4xl font-extrabold text-mel-400">{i + 1}</span>
              <h3 className="mt-2 text-lg font-bold text-white">{titulo}</h3>
              <p className="mt-2 leading-relaxed text-tinta-100">{texto}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}

const PUBLICOS = [
  {
    nome: 'Pesquisadores',
    texto: 'Menos tempo na triagem e dados organizados desde o campo.',
    itens: ['Identificação em lote', 'Correção manual registrada', 'Planilha Darwin Core para SiBBr e GBIF'],
  },
  {
    nome: 'Órgãos públicos',
    texto: 'Acompanhe onde cada espécie aparece e como as populações mudam.',
    itens: ['Mapa de ocorrências com filtros', 'Proteção da localização de espécies sensíveis', 'Dados por período e região'],
  },
  {
    nome: 'Estudantes',
    texto: 'Aprenda a reconhecer as espécies com fotos reais.',
    itens: ['Identificação rápida de uma foto', 'Fichas das espécies escritas por especialistas', 'Plano com preço acessível'],
  },
]

function ParaQuem() {
  return (
    <section aria-labelledby="titulo-quem" className={`${largura} py-16 sm:py-20`}>
      <Titulo id="titulo-quem">Para quem é</Titulo>
      <div className="mt-10 grid gap-10 md:grid-cols-3 md:gap-0 md:divide-x md:divide-tinta-100">
        {PUBLICOS.map((p) => (
          <div key={p.nome} className="md:px-8 md:first:pl-0 md:last:pr-0">
            <h3 className="font-display text-2xl font-bold text-tinta-900">{p.nome}</h3>
            <p className="mt-2 text-tinta-700">{p.texto}</p>
            <ul className="mt-4 space-y-2 text-sm text-tinta-800">
              {p.itens.map((i) => (
                <li key={i} className="flex gap-2">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-mel-500" aria-hidden />
                  {i}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  )
}

function Especies() {
  const lista = useQuery({
    queryKey: ['publico', 'especies'],
    queryFn: () => api<EspecieResumo[]>('/v1/publico/especies'),
  })
  const doModelo = lista.data?.filter((e) => e.reconhecida_pelo_modelo) ?? []
  if (!lista.data || doModelo.length === 0) return null
  return (
    <section aria-labelledby="titulo-especies" className="border-y border-tinta-100 bg-white py-16 sm:py-20">
      <div className={`${largura} grid gap-10 lg:grid-cols-[1fr_2fr]`}>
        <div>
          <Titulo id="titulo-especies">Espécies reconhecidas</Titulo>
          <p className="mt-4 text-tinta-700">
            O modelo atual identifica {doModelo.length} espécies de abelhas-das-orquídeas. A lista cresce a cada nova
            versão do modelo.
          </p>
          <Link to="/especies" className="mt-4 inline-block font-semibold text-tinta-700 underline">
            Ver as fichas das espécies
          </Link>
        </div>
        <ul className="divide-y divide-tinta-100 border-y border-tinta-100">
          {doModelo.map((e) => (
            <li key={e.id}>
              <Link to={`/especies/${e.id}`} className="group flex items-baseline justify-between gap-4 py-4">
                <span className="font-display text-2xl font-bold italic text-tinta-900 group-hover:text-tinta-700 sm:text-3xl">
                  {e.nome_cientifico}
                </span>
                <span className="shrink-0 text-sm text-tinta-500 group-hover:text-tinta-800">
                  {e.ficha_publicada ? 'Ler a ficha' : 'Ficha em preparação'}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

const PLANOS = [
  { nome: 'Estudante', para: 'Para aprender e fazer trabalhos da graduação e da pós.', itens: ['Identificação rápida', 'Coletas com limite mensal de fotos', 'Fichas das espécies'] },
  { nome: 'Pesquisador', para: 'Para quem processa coletas de campo com frequência.', itens: ['Mais fotos por mês', 'Exportação ZIP e Darwin Core', 'Mapa com localização exata de espécies sensíveis'] },
  { nome: 'Institucional', para: 'Para órgãos públicos, universidades e laboratórios.', itens: ['Vários usuários', 'Volume combinado com a equipe', 'Suporte para monitoramento'] },
]

function Planos({ aoEscolher }: { aoEscolher: () => void }) {
  return (
    <section id="planos" aria-labelledby="titulo-planos" className={`${largura} scroll-mt-4 py-16 sm:py-20`}>
      <Titulo id="titulo-planos">Planos</Titulo>
      <p className="mt-3 max-w-2xl text-tinta-700">
        O DBeeAS funciona por assinatura. Os valores serão divulgados na abertura das assinaturas; até lá, fale com a
        gente para participar da fase de testes.
      </p>
      <div className="mt-10 grid gap-6 md:grid-cols-3">
        {PLANOS.map((p) => (
          <div key={p.nome} className="flex flex-col rounded-2xl border border-tinta-100 bg-white p-6">
            <h3 className="font-display text-2xl font-bold text-tinta-900">{p.nome}</h3>
            <p className="mt-2 text-sm text-tinta-700">{p.para}</p>
            <ul className="mt-4 flex-1 space-y-2 text-sm text-tinta-800">
              {p.itens.map((i) => (
                <li key={i} className="flex gap-2">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-mel-500" aria-hidden />
                  {i}
                </li>
              ))}
            </ul>
            <button onClick={aoEscolher} className="mt-6 rounded-lg border border-tinta-700 px-4 py-2.5 text-sm font-semibold text-tinta-800 hover:bg-tinta-50">
              Quero saber mais
            </button>
          </div>
        ))}
      </div>
    </section>
  )
}

const ASSUNTOS: [string, string][] = [
  ['duvida', 'Dúvida'],
  ['planos', 'Planos e assinaturas'],
  ['institucional', 'Uso institucional'],
  ['parceria', 'Parceria'],
  ['imprensa', 'Imprensa'],
  ['outro', 'Outro assunto'],
]

function Contato({ assunto, setAssunto }: { assunto: string; setAssunto: (a: string) => void }) {
  const [enviado, setEnviado] = useState<string | null>(null)
  const enviar = useMutation({
    mutationFn: (dados: Record<string, string>) =>
      api<{ mensagem: string }>('/v1/publico/contato', { method: 'POST', body: dados }),
    onSuccess: (r) => setEnviado(r.mensagem),
  })
  const aoEnviar = (ev: FormEvent<HTMLFormElement>) => {
    ev.preventDefault()
    const dados = Object.fromEntries(new FormData(ev.currentTarget)) as Record<string, string>
    enviar.mutate({ ...dados, assunto })
  }

  return (
    <section id="contato" aria-labelledby="titulo-contato" className="scroll-mt-4 border-t border-tinta-100 bg-white py-16 sm:py-20">
      <div className={`${largura} grid gap-10 lg:grid-cols-[1fr_1.4fr]`}>
        <div>
          <Titulo id="titulo-contato">Contato</Titulo>
          <p className="mt-4 text-tinta-700">
            Dúvidas, uso em projetos de monitoramento, parcerias ou interesse nos planos: escreva para a gente.
          </p>
          <p className="mt-4 text-tinta-700">
            Ou mande um e-mail para{' '}
            <a href="mailto:contato@dbeeas.com.br" className="font-semibold text-tinta-800 underline">contato@dbeeas.com.br</a>.
          </p>
        </div>
        {enviado ? (
          <Alerta tipo="sucesso">{enviado}</Alerta>
        ) : (
          <form onSubmit={aoEnviar} className="grid gap-4 sm:grid-cols-2">
            <Campo rotulo="Nome" name="nome" required minLength={2} maxLength={120} autoComplete="name" />
            <Campo rotulo="E-mail" name="email" type="email" required autoComplete="email" />
            <Campo rotulo="Instituição (opcional)" name="instituicao" maxLength={200} autoComplete="organization" />
            <Selecao rotulo="Assunto" value={assunto} onChange={(e) => setAssunto(e.target.value)}>
              {ASSUNTOS.map(([v, n]) => (
                <option key={v} value={v}>{n}</option>
              ))}
            </Selecao>
            <AreaTexto rotulo="Mensagem" name="mensagem" required minLength={10} maxLength={5000} rows={5} className="sm:col-span-2" />
            {/* Campo escondido contra robôs: pessoas não o veem nem preenchem */}
            <div aria-hidden="true" className="absolute -left-[9999px] h-px w-px overflow-hidden">
              <label>
                Site <input name="site" tabIndex={-1} autoComplete="off" />
              </label>
            </div>
            {enviar.error && <div className="sm:col-span-2"><Alerta>{mensagemErro(enviar.error)}</Alerta></div>}
            <div className="sm:col-span-2">
              <Botao type="submit" carregando={enviar.isPending}>Enviar mensagem</Botao>
            </div>
          </form>
        )}
      </div>
    </section>
  )
}

export default function Inicio() {
  const [assunto, setAssunto] = useState('duvida')
  // Links como /#contato (do rodapé) levam direto à seção
  const { hash } = useLocation()
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView()
  }, [hash])
  const escolherPlano = () => {
    setAssunto('planos')
    document.getElementById('contato')?.scrollIntoView({ behavior: 'smooth' })
  }
  return (
    <>
      <Abertura />
      <ComoFunciona />
      <ParaQuem />
      <Especies />
      <Planos aoEscolher={escolherPlano} />
      <Contato assunto={assunto} setAssunto={setAssunto} />
    </>
  )
}
