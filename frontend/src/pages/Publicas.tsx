/** Páginas públicas. A página inicial completa será feita na etapa 6. */
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export function Inicio() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:py-24">
      <p className="text-sm font-semibold uppercase tracking-widest text-mel-700">Identificação de abelhas pela asa</p>
      <h1 className="mt-3 max-w-3xl text-4xl font-bold leading-tight text-tinta-900 sm:text-5xl">
        Envie a foto da asa. O DBeeAS identifica a espécie.
      </h1>
      <p className="mt-5 max-w-2xl text-lg text-tinta-500">
        Um sistema de inteligência artificial para pesquisadores, órgãos públicos e estudantes identificarem
        abelhas, organizarem coletas e acompanharem onde cada espécie é encontrada.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <Link to="/cadastrar" className="rounded-lg bg-mel-500 px-5 py-3 font-semibold text-tinta-900 hover:bg-mel-400">
          Criar conta
        </Link>
        <Link to="/entrar" className="rounded-lg border border-tinta-100 bg-white px-5 py-3 font-semibold text-tinta-800 hover:bg-tinta-50">
          Já tenho conta
        </Link>
      </div>
    </section>
  )
}

function Documento({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-bold text-tinta-900">{titulo}</h1>
      <p className="mt-4 rounded-lg border border-mel-200 bg-mel-50 px-4 py-3 text-sm text-mel-700">
        Rascunho: este texto precisa ser revisado por um profissional do direito antes do lançamento.
      </p>
      <div className="mt-8 space-y-4 leading-relaxed text-tinta-800 [&_h2]:mt-8 [&_h2]:text-xl [&_h2]:font-bold [&_h2]:text-tinta-900">
        {children}
      </div>
    </article>
  )
}

export function Termos() {
  return (
    <Documento titulo="Termos de uso">
      <p>
        O DBeeAS é um serviço da RCGJ Sistemas Inteligentes que identifica espécies de abelhas a partir de fotos
        da asa, usando inteligência artificial.
      </p>
      <h2>Uso do serviço</h2>
      <p>
        As identificações são automáticas e podem conter erros. Elas servem de apoio e não substituem a
        análise de um especialista. Você é responsável pelas fotos e dados que envia.
      </p>
      <h2>Conta</h2>
      <p>
        Mantenha sua senha em segredo. Podemos suspender contas usadas de forma abusiva ou contrária a estes
        termos.
      </p>
      <h2>Contato</h2>
      <p>Dúvidas sobre estes termos podem ser enviadas para contato@dbeeas.com.br.</p>
    </Documento>
  )
}

export function Privacidade() {
  return (
    <Documento titulo="Política de privacidade">
      <h2>Quais dados coletamos</h2>
      <p>
        Nome, e-mail, perfil, instituição (opcional), as fotos que você envia e os dados delas, como data e
        localização da coleta.
      </p>
      <h2>Para que usamos</h2>
      <p>
        Para identificar as espécies, organizar suas coletas e gerar mapas e relatórios. Só usamos suas fotos
        para melhorar o modelo de identificação se você autorizar, e você pode mudar essa escolha a qualquer
        momento em “Minha conta”.
      </p>
      <h2>Mapa de ocorrências</h2>
      <p>
        Por padrão, as ocorrências das suas coletas (espécie, data e ponto) aparecem no mapa geral da plataforma,
        para apoiar a pesquisa e o monitoramento ambiental. Outras pessoas não veem suas fotos, o nome da coleta
        nem quem coletou. Você pode tirar qualquer coleta do mapa geral ao editá-la.
      </p>
      <h2>Localização de espécies sensíveis</h2>
      <p>
        Para proteger espécies ameaçadas, a localização exata dessas espécies só é mostrada ao dono da foto,
        a pesquisadores e aos administradores. Os demais usuários veem apenas uma área aproximada.
      </p>
      <h2>Seus direitos (LGPD)</h2>
      <p>
        Você pode baixar uma cópia dos seus dados e excluir sua conta a qualquer momento em “Minha conta”.
        Para outros pedidos, escreva para contato@dbeeas.com.br.
      </p>
      <h2>Onde os dados ficam</h2>
      <p>Os dados ficam em servidores localizados no Brasil.</p>
    </Documento>
  )
}

export function NaoEncontrada() {
  return (
    <section className="mx-auto max-w-xl px-4 py-24 text-center">
      <p className="text-6xl font-bold text-mel-500">404</p>
      <h1 className="mt-4 text-2xl font-bold text-tinta-900">Página não encontrada</h1>
      <Link to="/" className="mt-6 inline-block font-semibold text-tinta-700 underline">Voltar ao início</Link>
    </section>
  )
}
