/** Filtros da grade de fotos de uma coleta. */

export type Filtro =
  | { tipo: 'todas' }
  | { tipo: 'especie'; id: number; nome: string }
  | { tipo: 'nao_identificadas' }
  | { tipo: 'revisadas' }
  | { tipo: 'pendentes' }
  | { tipo: 'erro' }

export const mesmoFiltro = (a: Filtro, b: Filtro) =>
  a.tipo === b.tipo && (a.tipo !== 'especie' || (b.tipo === 'especie' && a.id === b.id))

/** Parâmetros da API para o filtro escolhido */
export function parametrosFiltro(f: Filtro): Record<string, string> {
  switch (f.tipo) {
    case 'especie':
      return { especie_id: String(f.id) }
    case 'nao_identificadas':
    case 'revisadas':
    case 'pendentes':
      return { grupo: f.tipo }
    case 'erro':
      return { status: 'erro' }
    default:
      return {}
  }
}
