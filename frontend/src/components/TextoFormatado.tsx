/**
 * Mostra os textos das fichas com uma formatação simples, sem aceitar HTML
 * (assim ninguém consegue colocar código na página):
 *
 *   linha em branco      → novo parágrafo
 *   "- " no começo       → item de lista
 *   **texto**            → negrito
 *   *texto*              → itálico (nomes científicos)
 *   https://...          → link
 */
import type { ReactNode } from 'react'

const MARCAS = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|https?:\/\/[^\s)]+)/g

function textoEmLinha(texto: string): ReactNode[] {
  return texto.split(MARCAS).map((parte, i) => {
    if (parte.startsWith('**') && parte.endsWith('**') && parte.length > 4) return <strong key={i}>{parte.slice(2, -2)}</strong>
    if (parte.startsWith('*') && parte.endsWith('*') && parte.length > 2) return <em key={i}>{parte.slice(1, -1)}</em>
    if (/^https?:\/\//.test(parte)) {
      const url = parte.replace(/[.,;]+$/, '')
      return (
        <span key={i}>
          <a href={url} target="_blank" rel="noopener noreferrer" className="break-all text-tinta-700 underline">
            {url}
          </a>
          {parte.slice(url.length)}
        </span>
      )
    }
    return parte
  })
}

/** Uma linha só (sem parágrafos), com negrito, itálico e links. */
export function TextoEmLinha({ texto }: { texto: string }) {
  return <>{textoEmLinha(texto)}</>
}

export default function TextoFormatado({ texto, className = '' }: { texto: string | null | undefined; className?: string }) {
  if (!texto) return null
  const blocos = texto.trim().split(/\n\s*\n/)
  return (
    <div className={`space-y-3 ${className}`}>
      {blocos.map((bloco, i) => {
        const linhas = bloco.split('\n')
        if (linhas.every((l) => /^\s*-\s+/.test(l))) {
          return (
            <ul key={i} className="list-disc space-y-1 pl-5 marker:text-mel-600">
              {linhas.map((l, j) => (
                <li key={j}>{textoEmLinha(l.replace(/^\s*-\s+/, ''))}</li>
              ))}
            </ul>
          )
        }
        return (
          <p key={i}>
            {linhas.map((l, j) => (
              <span key={j}>
                {j > 0 && <br />}
                {textoEmLinha(l)}
              </span>
            ))}
          </p>
        )
      })}
    </div>
  )
}
