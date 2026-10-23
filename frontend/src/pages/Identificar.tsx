/** Identificação rápida de uma foto (nada é guardado). */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Alerta, Botao, Cartao } from '../components/ui'
import { API_URL, ErroApi, mensagemErro, obterToken, renovarSessao } from '../lib/api'
import { pct, type Deteccao } from '../lib/coletas'

interface Resultado {
  identificada: boolean
  especie: string | null
  confianca: number | null
  mensagem: string | null
  deteccoes: Deteccao[]
  imagem_anotada?: string
}

async function identificar(arquivo: File): Promise<Resultado> {
  const form = new FormData()
  form.append('arquivo', arquivo)
  const enviar = (token: string | null) =>
    fetch(`${API_URL}/v1/identificar`, {
      method: 'POST',
      credentials: 'include',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    })
  let r = await enviar(obterToken())
  if (r.status === 401) {
    const sessao = await renovarSessao()
    if (sessao) r = await enviar(sessao.access_token)
  }
  const corpo = await r.json().catch(() => null)
  if (!r.ok) throw new ErroApi(r.status, corpo?.detail ?? 'Não foi possível identificar.')
  return corpo
}

export default function Identificar() {
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [previa, setPrevia] = useState<string | null>(null)
  const [resultado, setResultado] = useState<Resultado | null>(null)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  function escolher(f: File | undefined) {
    if (!f) return
    if (previa) URL.revokeObjectURL(previa)
    setArquivo(f)
    setPrevia(URL.createObjectURL(f))
    setResultado(null)
    setErro('')
  }

  async function enviar() {
    if (!arquivo) return
    setEnviando(true)
    setErro('')
    try {
      setResultado(await identificar(arquivo))
    } catch (e) {
      setErro(mensagemErro(e))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-tinta-900">Identificação rápida</h1>
        <p className="mt-1 text-sm text-tinta-500">
          Envie uma foto da asa e veja a espécie na hora. A foto não fica guardada. Para várias fotos e para guardar os
          resultados, use as <Link to="/coletas" className="font-semibold underline">coletas</Link>.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Cartao className="space-y-4">
          <label className="block cursor-pointer rounded-xl border-2 border-dashed border-tinta-100 p-4 text-center hover:border-mel-400">
            {previa ? (
              <img src={resultado?.imagem_anotada ? `data:image/jpeg;base64,${resultado.imagem_anotada}` : previa} alt="Foto escolhida" className="mx-auto max-h-80 rounded-lg" />
            ) : (
              <span className="block py-10 text-sm text-tinta-500">Toque para escolher ou tirar uma foto</span>
            )}
            <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => escolher(e.target.files?.[0])} />
          </label>
          <Botao className="w-full" disabled={!arquivo} carregando={enviando} onClick={enviar}>
            Identificar
          </Botao>
        </Cartao>

        <Cartao>
          <h2 className="text-xs font-semibold uppercase tracking-wide text-tinta-500">Resultado</h2>
          {erro && <div className="mt-3"><Alerta>{erro}</Alerta></div>}
          {!resultado && !erro && <p className="mt-3 text-sm text-tinta-500">O resultado aparece aqui.</p>}
          {resultado && (
            <div className="mt-3 space-y-4">
              {resultado.identificada ? (
                <div>
                  <p className="text-2xl font-bold italic text-tinta-900">{resultado.especie}</p>
                  <p className="text-sm text-tinta-500">Confiança do modelo: {pct(resultado.confianca)}</p>
                </div>
              ) : (
                <Alerta tipo="info">{resultado.mensagem ?? 'Não foi possível identificar. Tente outra foto da asa.'}</Alerta>
              )}
              {resultado.deteccoes.length > 1 && (
                <div>
                  <p className="text-xs font-semibold text-tinta-500">Outras detecções</p>
                  <ul className="mt-1 space-y-1 text-sm">
                    {resultado.deteccoes.slice(1).map((d, i) => (
                      <li key={i} className="flex justify-between"><span className="italic">{d.especie}</span><span>{pct(d.confianca)}</span></li>
                    ))}
                  </ul>
                </div>
              )}
              <p className="text-xs text-tinta-300">
                A identificação é automática e pode conter erros. Ela não substitui a análise de um especialista.
              </p>
            </div>
          )}
        </Cartao>
      </div>
    </div>
  )
}
