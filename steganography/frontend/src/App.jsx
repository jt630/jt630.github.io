import { useState } from 'react'
import EncodePanel from './components/EncodePanel'
import DecodePanel from './components/DecodePanel'
import AnalyzePanel from './components/AnalyzePanel'

/**
 * App
 *
 * State held here so Encode→Analyze and Decode→Analyze both work.
 * `activeReceipt`  — the Receipt object forwarded to AnalyzePanel
 * `analyzeSource`  — "encode" | "decode" | null (for display label)
 */
export default function App() {
  const [activeReceipt, setActiveReceipt] = useState(null)
  const [analyzeSource, setAnalyzeSource] = useState(null)

  const handleEncoded = (receipt, _encodeResult) => {
    setActiveReceipt(receipt)
    setAnalyzeSource('encode')
  }

  const handleDecoded = (receipt, _decodeResult) => {
    setActiveReceipt(receipt)
    setAnalyzeSource('decode')
  }

  return (
    <>
      <header className="app-header">
        <h1>Steg Receipt</h1>
        <span className="subtitle">steganographic receipt encoder / decoder / analyzer</span>
        {activeReceipt && (
          <span style={{
            marginLeft: 'auto',
            fontSize: 11,
            fontFamily: 'var(--mono)',
            color: 'var(--gold)',
            border: '1px solid var(--gold)',
            borderRadius: 4,
            padding: '2px 10px',
          }}>
            {analyzeSource === 'encode' ? '↑ from encode' : '↓ from decode'} · {activeReceipt.store_name}
          </span>
        )}
      </header>

      <main className="app-body">
        <EncodePanel onEncoded={handleEncoded} />
        <DecodePanel onDecoded={handleDecoded} />
        <AnalyzePanel receipt={activeReceipt} />
      </main>
    </>
  )
}
