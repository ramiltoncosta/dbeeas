/** Mapa com os pontos onde as espécies desta coleta foram encontradas. */
import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import MapaOcorrencias from '../../components/MapaOcorrencias'
import { api } from '../../lib/api'
import { COR_OUTRAS, coresPorEspecie, type Ocorrencia, type Propriedades } from '../../lib/mapa'

interface Props {
  coletaId: string
  identificadas: number
  aoAbrirFoto: (fotoId: string) => void
}

export default function MapaDaColeta({ coletaId, identificadas, aoAbrirFoto }: Props) {
  const dados = useQuery({
    queryKey: ['mapa', 'coleta', coletaId],
    // "todas" + coleta: o dono vê a própria coleta e o administrador vê a de qualquer pessoa
    queryFn: () =>
      api<GeoJSON.FeatureCollection<GeoJSON.Point, Propriedades>>(
        `/v1/mapa/ocorrencias?escopo=todas&coleta_id=${coletaId}`,
      ),
  })
  const ocorrencias = useMemo(() => (dados.data?.features ?? []) as Ocorrencia[], [dados.data])
  const { cor, legenda } = useMemo(() => coresPorEspecie(ocorrencias), [ocorrencias])
  const semLocal = Math.max(identificadas - ocorrencias.length, 0)
  const outras = legenda.filter((e) => e.cor === COR_OUTRAS)

  return (
    <section className="flex flex-col rounded-2xl border border-tinta-100 bg-white p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-bold text-tinta-800">Onde foram encontradas</h2>
        <Link to={`/mapa?coleta=${coletaId}`} className="text-xs font-semibold text-tinta-500 hover:text-tinta-800">
          Abrir no mapa completo →
        </Link>
      </div>

      {dados.isSuccess && ocorrencias.length === 0 ? (
        <div className="flex flex-1 items-center justify-center rounded-lg bg-tinta-50 px-6 py-10 text-center text-sm text-tinta-500">
          {identificadas === 0
            ? 'Os pontos aparecem aqui quando as fotos forem identificadas.'
            : 'As fotos identificadas não têm localização. Marque o ponto da coleta em “Editar” ou a localização de cada foto.'}
        </div>
      ) : (
        <>
          <div className="h-96 overflow-hidden rounded-lg border border-tinta-100 lg:flex-1">
            <MapaOcorrencias ocorrencias={ocorrencias} cor={cor} aoAbrirFoto={aoAbrirFoto} className="h-full min-h-96 w-full" />
          </div>
          <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Legenda do mapa">
            {legenda
              .filter((e) => e.cor !== COR_OUTRAS)
              .map((e) => (
                <li key={e.id} className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: e.cor }} aria-hidden />
                  <span className="italic text-tinta-800">{e.nome}</span>
                  <span className="text-tinta-500">{e.n}</span>
                </li>
              ))}
            {outras.length > 0 && (
              <li className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: COR_OUTRAS }} aria-hidden />
                <span className="text-tinta-800">Outras espécies</span>
                <span className="text-tinta-500">{outras.reduce((s, e) => s + e.n, 0)}</span>
              </li>
            )}
          </ul>
          <p className="mt-2 text-xs text-tinta-500">
            Passe o mouse sobre um ponto para ver a foto; clique para abri-la.
          </p>
          {semLocal > 0 && (
            <p className="mt-2 text-xs text-tinta-500">
              {semLocal} foto(s) identificada(s) sem localização não aparecem no mapa.
            </p>
          )}
        </>
      )}
    </section>
  )
}
