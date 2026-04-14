import { useState } from 'react'

const API = 'http://localhost:8000'

const MODES = ['expense', 'split', 'warranty', 'returns']

function renderDetails(details) {
  if (!details || typeof details !== 'object') return null

  const entries = Object.entries(details)
  if (entries.length === 0) return null

  return (
    <div className="ai-details-grid">
      {entries.map(([key, val]) => (
        <div className="ai-detail-item" key={key}>
          <div className="ai-detail-key">{key.replace(/_/g, ' ')}</div>
          <div className="ai-detail-val">
            {typeof val === 'object' ? JSON.stringify(val, null, 2) : String(val)}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function AnalyzePanel({ receipt }) {
  const [mode, setMode] = useState('expense')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const handleAnalyze = async () => {
    if (!receipt) return
    setError(null)
    setResult(null)
    setLoading(true)

    try {
      const res = await fetch(`${API}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ receipt, mode }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || res.statusText)
      }

      const data = await res.json()
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // Reset result when mode changes
  const selectMode = (m) => {
    setMode(m)
    setResult(null)
    setError(null)
  }

  const noReceipt = !receipt

  return (
    <div className="panel panel-analyze">
      <div className="panel-title">03 / Analyze</div>

      {noReceipt ? (
        <p style={{ color: 'var(--muted)', fontSize: 13 }}>
          Encode or decode a receipt first — the analyzed data will appear here.
        </p>
      ) : (
        <>
          {/* Receipt summary line */}
          <div style={{ marginBottom: 16, fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--muted)' }}>
            <span style={{ color: 'var(--text)' }}>{receipt.store_name}</span>
            {receipt.date && <> · {receipt.date}</>}
            {receipt.total != null && (
              <span style={{ color: 'var(--gold)', marginLeft: 12, fontSize: 14 }}>
                ${receipt.total.toFixed(2)}
              </span>
            )}
          </div>

          {/* Mode selector */}
          <div className="mode-selector">
            {MODES.map(m => (
              <button
                key={m}
                className={`mode-btn${mode === m ? ' active' : ''}`}
                onClick={() => selectMode(m)}
              >
                {m}
              </button>
            ))}
          </div>

          {/* Mode descriptions */}
          <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
            {mode === 'expense'  && 'Categorize items for expense reporting — business vs. personal, category tags.'}
            {mode === 'split'    && 'Split the bill fairly between multiple people.'}
            {mode === 'warranty' && 'Identify items with warranty implications and track purchase dates.'}
            {mode === 'returns'  && 'Flag items eligible for return or price-match within standard policies.'}
          </p>

          <button
            className="btn btn-primary"
            onClick={handleAnalyze}
            disabled={loading}
          >
            {loading
              ? <><span className="spinner">⟳</span> Asking Claude…</>
              : `Ask Claude — ${mode}`
            }
          </button>

          {error && <div className="error-msg">Error: {error}</div>}

          {result && (
            <div className="ai-response-card">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <span className="badge" style={{ background: '#1a1000', color: 'var(--gold)', border: '1px solid var(--gold)' }}>
                  {result.mode?.toUpperCase()}
                </span>
                <span style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--mono)' }}>
                  AI Analysis
                </span>
              </div>

              {result.summary && (
                <p className="ai-summary">{result.summary}</p>
              )}

              {result.details && Object.keys(result.details).length > 0 && (
                <>
                  <hr className="divider" />
                  {renderDetails(result.details)}
                </>
              )}

              {result.raw_response && (
                <details style={{ marginTop: 14 }}>
                  <summary style={{ cursor: 'pointer', fontSize: 11, color: 'var(--muted)', letterSpacing: 1, textTransform: 'uppercase' }}>
                    Raw Response
                  </summary>
                  <pre style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 11,
                    color: 'var(--muted)',
                    marginTop: 8,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    background: 'var(--bg)',
                    padding: '10px 12px',
                    borderRadius: 4,
                    border: '1px solid var(--border)',
                    maxHeight: 300,
                    overflowY: 'auto',
                  }}>
                    {result.raw_response}
                  </pre>
                </details>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
