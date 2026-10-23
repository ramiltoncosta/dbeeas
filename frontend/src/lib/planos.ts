/** Planos e assinaturas. */
import { useQuery } from '@tanstack/react-query'
import { api } from './api'

export interface Plano {
  id: number
  codigo: string
  nome: string
  descricao: string | null
  preco_mensal_centavos: number | null
  limite_fotos_mes: number | null
  permite_exportacao: boolean
  publico: boolean
  ordem: number
}

export type StatusAssinatura = 'teste' | 'pendente' | 'ativa' | 'suspensa' | 'cancelada'

export interface Assinatura {
  id: string
  plano: Plano
  status: StatusAssinatura
  inicio: string
  fim: string | null
  origem: string
  observacao: string | null
  criado_em: string
  alterado_por: string | null
}

export interface MeuPlano {
  status: StatusAssinatura | 'expirada' | 'sem_plano' | 'ilimitado'
  plano: Plano | null
  assinatura: Assinatura | null
  uso: {
    mes: string
    fotos: number
    identificacoes_rapidas: number
    usadas: number
    limite: number | null
    restantes: number | null
  }
  pode_enviar: boolean
  motivo_bloqueio: string | null
  permite_exportacao: boolean
  pedido: Assinatura | null
}

export const NOMES_STATUS: Record<string, string> = {
  teste: 'Teste gratuito',
  pendente: 'Pedido em análise',
  ativa: 'Ativa',
  suspensa: 'Suspensa',
  cancelada: 'Cancelada',
  expirada: 'Vencida',
  sem_plano: 'Sem plano',
  ilimitado: 'Administrador (sem limite)',
}

/** Cor do selo de cada situação */
export const COR_STATUS: Record<string, string> = {
  teste: 'bg-mel-100 text-mel-700',
  pendente: 'bg-mel-100 text-mel-700',
  ativa: 'bg-emerald-50 text-emerald-800',
  ilimitado: 'bg-emerald-50 text-emerald-800',
  suspensa: 'bg-red-50 text-red-800',
  cancelada: 'bg-tinta-50 text-tinta-700',
  expirada: 'bg-red-50 text-red-800',
  sem_plano: 'bg-tinta-50 text-tinta-700',
}

export const preco = (centavos: number | null) =>
  centavos == null
    ? null
    : (centavos / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

export const limiteTexto = (limite: number | null) =>
  limite == null ? 'Fotos sem limite' : `Até ${limite.toLocaleString('pt-BR')} fotos por mês`

export const dataCurta = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('pt-BR') : null)

export function useMeuPlano(ativo = true) {
  return useQuery({ queryKey: ['meu-plano'], queryFn: () => api<MeuPlano>('/v1/eu/plano'), enabled: ativo })
}
