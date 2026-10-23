/**
 * Resultado da coleta: gráfico de barras com a quantidade e a porcentagem de cada espécie.
 * Uma barra por espécie, ordenadas da maior para a menor, com os números escritos ao lado
 * (não depende só da cor). Clicar numa espécie filtra as fotos.
 */
import { pct, type ResumoColeta } from '../../lib/coletas'
import { mesmoFiltro, type Filtro } from '../../lib/filtros'

interface Props {
  resumo: ResumoColeta
  filtro: Filtro
  aoFiltrar: (f: Filtro) => void
}

export function GraficoEspecies({ resumo, filtro, aoFiltrar }: Props) {
  if (!resumo.identificadas) {
    return (
      <p className="text-sm text-tinta-500">
        {resumo.pendentes > 0
          ? 'O gráfico aparece quando as primeiras fotos forem identificadas.'
          : 'Nenhuma foto identificada nesta coleta.'}
      </p>
    )
  }
  const maior = Math.max(...resumo.especies.map((e) => e.quantidade))

  return (
    <figure>
      <figcaption className="mb-4 text-xs text-tinta-500">
        Porcentagens sobre as {resumo.identificadas} foto(s) identificada(s).
        {resumo.nao_identificadas > 0 && ` As ${resumo.nao_identificadas} não identificada(s) ficam de fora.`}
      </figcaption>
      <ul className="space-y-1">
        {resumo.especies.map((e) => {
          const ativo = filtro.tipo === 'especie' && filtro.id === e.id
          const dica = [
            `${e.nome}: ${e.quantidade} foto(s), ${e.porcentagem.toLocaleString('pt-BR')}%`,
            e.revisadas ? `${e.revisadas} revisada(s)` : null,
            e.confianca_media != null ? `confiança média do modelo ${pct(e.confianca_media)}` : null,
          ]
            .filter(Boolean)
            .join(' · ')
          return (
            <li key={e.id}>
              <button
                title={dica}
                aria-label={dica}
                aria-pressed={ativo}
                onClick={() => aoFiltrar(ativo ? { tipo: 'todas' } : { tipo: 'especie', id: e.id, nome: e.nome })}
                className={`group grid w-full grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 rounded-lg px-2 py-1.5 text-left transition sm:grid-cols-[minmax(0,14rem)_1fr_auto] ${
                  ativo ? 'bg-mel-50 ring-1 ring-mel-400' : 'hover:bg-tinta-50'
                }`}
              >
                <span className="truncate text-sm font-semibold italic text-tinta-800">{e.nome}</span>
                <span className="order-last col-span-2 h-3 overflow-hidden rounded-r sm:order-none sm:col-span-1">
                  <span
                    className="block h-full rounded-r bg-mel-500 transition-all group-hover:bg-mel-600"
                    style={{ width: `${Math.max((e.quantidade / maior) * 100, 2)}%` }}
                  />
                </span>
                <span className="whitespace-nowrap text-right text-sm tabular-nums text-tinta-700">
                  <span className="font-semibold">{e.porcentagem.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%</span>
                  <span className="text-tinta-500"> · {e.quantidade}</span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </figure>
  )
}

interface FiltrosProps {
  resumo: ResumoColeta
  filtro: Filtro
  aoFiltrar: (f: Filtro) => void
}

export function FiltrosFotos({ resumo, filtro, aoFiltrar }: FiltrosProps) {
  const opcoes: { f: Filtro; rotulo: string; n: number }[] = [
    { f: { tipo: 'todas' }, rotulo: 'Todas', n: resumo.total },
    ...resumo.especies.map((e) => ({
      f: { tipo: 'especie' as const, id: e.id, nome: e.nome },
      rotulo: e.nome,
      n: e.quantidade,
    })),
    { f: { tipo: 'nao_identificadas' }, rotulo: 'Não identificadas', n: resumo.nao_identificadas },
    {
      f: { tipo: 'para_revisar' },
      rotulo: `Para conferir (confiança < ${Math.round(resumo.limite_confianca_revisao * 100)}%)`,
      n: resumo.para_revisar,
    },
    { f: { tipo: 'revisadas' }, rotulo: 'Revisadas', n: resumo.revisadas },
    { f: { tipo: 'pendentes' }, rotulo: 'Na fila', n: resumo.pendentes },
    { f: { tipo: 'erro' }, rotulo: 'Com erro', n: resumo.erro },
  ]
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar fotos">
      {opcoes
        .filter((o) => o.n > 0 || o.f.tipo === 'todas' || mesmoFiltro(o.f, filtro))
        .map((o) => {
          const ativo = mesmoFiltro(o.f, filtro)
          return (
            <button
              key={o.f.tipo === 'especie' ? `e${o.f.id}` : o.f.tipo}
              onClick={() => aoFiltrar(o.f)}
              aria-pressed={ativo}
              className={`rounded-full border px-3 py-1 text-sm transition ${
                ativo
                  ? 'border-tinta-700 bg-tinta-700 text-white'
                  : 'border-tinta-100 bg-white text-tinta-800 hover:border-mel-400'
              } ${o.f.tipo === 'especie' ? 'italic' : ''}`}
            >
              {o.rotulo} <span className={`not-italic ${ativo ? 'text-tinta-100' : 'text-tinta-500'}`}>{o.n}</span>
            </button>
          )
        })}
    </div>
  )
}
