/**
 * Desenho de uma asa anterior de abelha (nervuras e células), como aparece numa
 * foto feita na lupa. Com `deteccao`, mostra a caixa e o rótulo que o modelo
 * desenha ao identificar a espécie.
 */
interface Props {
  deteccao?: { especie: string; confianca: number }
  className?: string
}

const NERVURAS = [
  // subcosta e radial até o estigma
  'M34 147 C110 112 220 94 330 90',
  // média
  'M38 160 C130 150 220 148 300 150',
  // cúbito
  'M44 173 C150 181 240 190 320 186 C380 184 430 180 472 176',
  // anal
  'M42 182 C100 202 160 211 214 213',
  // borda inferior das submarginais
  'M300 150 C360 160 440 168 505 160',
  // nervuras transversais
  'M300 150 L320 186',
  'M381 159 L392 183',
  'M396 118 L381 159',
  'M446 120 L441 166',
  'M497 116 L503 161',
  'M214 213 L240 190',
]

export default function Asa({ deteccao, className = '' }: Props) {
  const caixa = { x: 14, y: 52, w: 624, h: 196 }
  const perimetro = 2 * (caixa.w + caixa.h)
  const rotulo = deteccao ? `${deteccao.especie} ${Math.round(deteccao.confianca * 100)}%` : ''
  return (
    <svg viewBox="0 0 652 262" className={className} role="img" aria-label={deteccao ? `Asa identificada como ${rotulo}` : 'Desenho de uma asa de abelha'}>
      {/* membrana */}
      <path
        d="M22 150 C40 120 90 95 170 82 C300 62 470 58 560 78 C610 90 632 112 628 135 C624 165 590 190 520 205 C400 232 250 240 150 222 C90 212 40 190 22 150 Z"
        fill="#d6e4e9"
        fillOpacity="0.45"
        stroke="#1f4e5f"
        strokeWidth="2.5"
      />
      {/* célula marginal */}
      <path d="M370 88 C430 86 490 92 526 110 C500 118 450 120 396 118 Z" fill="#8fb0bd" fillOpacity="0.25" stroke="#1f4e5f" strokeWidth="2" />
      <g fill="none" stroke="#1f4e5f" strokeWidth="2" strokeLinecap="round">
        {NERVURAS.map((d) => (
          <path key={d} d={d} />
        ))}
      </g>
      {/* estigma */}
      <path d="M328 86 C345 82 362 84 372 88 C360 93 342 94 328 92 Z" fill="#183d4a" />

      {deteccao && (
        <g>
          <rect
            className="dbeeas-caixa"
            style={{ ['--perimetro' as string]: perimetro }}
            x={caixa.x}
            y={caixa.y}
            width={caixa.w}
            height={caixa.h}
            rx="4"
            fill="none"
            stroke="#e0a23a"
            strokeWidth="3"
          />
          <g className="dbeeas-rotulo">
            <rect x={caixa.x - 1.5} y={caixa.y - 30} width={rotulo.length * 9.6 + 20} height="30" rx="4" fill="#e0a23a" />
            <text x={caixa.x + 9} y={caixa.y - 10} fontSize="16" fontWeight="600" fill="#102a33" fontFamily="Inter Variable, Inter, sans-serif">
              <tspan fontStyle="italic">{deteccao.especie}</tspan> {Math.round(deteccao.confianca * 100)}%
            </text>
          </g>
        </g>
      )}
    </svg>
  )
}
