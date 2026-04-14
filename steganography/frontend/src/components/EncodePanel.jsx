import { useState } from 'react'

const API = 'http://localhost:8000'

const EMPTY_ITEM = () => ({ name: '', qty: 1, unit_price: 0, total: 0 })

const TODAY = new Date().toISOString().split('T')[0]

function calcItem(item) {
  return { ...item, total: parseFloat((item.qty * item.unit_price).toFixed(2)) }
}

export default function EncodePanel({ onEncoded }) {
  const [form, setForm] = useState({
    store_name: '',
    store_address: '',
    date: TODAY,
    transaction_id: '',
    tax_rate: 8.75,
    payment_method: '',
    cashier: '',
  })
  const [items, setItems] = useState([EMPTY_ITEM()])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  // ── Derived totals ──────────────────────────────────────────────
  const subtotal = items.reduce((s, it) => s + (it.total || 0), 0)
  const taxRate = parseFloat(form.tax_rate) / 100 || 0
  const taxAmount = parseFloat((subtotal * taxRate).toFixed(2))
  const total = parseFloat((subtotal + taxAmount).toFixed(2))

  // ── Form helpers ────────────────────────────────────────────────
  const setField = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const updateItem = (i, k, v) => {
    setItems(prev => {
      const next = prev.map((it, idx) => {
        if (idx !== i) return it
        const updated = { ...it, [k]: v }
        return calcItem(updated)
      })
      return next
    })
  }

  const addItem = () => setItems(prev => [...prev, EMPTY_ITEM()])
  const removeItem = (i) => setItems(prev => prev.filter((_, idx) => idx !== i))

  // ── Submit ──────────────────────────────────────────────────────
  const handleSubmit = async () => {
    setError(null)
    setResult(null)
    setLoading(true)

    const receipt = {
      store_name: form.store_name,
      store_address: form.store_address || undefined,
      date: form.date,
      transaction_id: form.transaction_id || undefined,
      items: items.map(it => ({
        name: it.name,
        qty: parseFloat(it.qty) || 1,
        unit_price: parseFloat(it.unit_price) || 0,
        total: parseFloat(it.total) || 0,
      })),
      subtotal: parseFloat(subtotal.toFixed(2)),
      tax_rate: taxRate || undefined,
      tax_amount: taxAmount,
      total,
      payment_method: form.payment_method || undefined,
      cashier: form.cashier || undefined,
    }

    try {
      const res = await fetch(`${API}/full-flow`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ receipt, texture_size: 512, opacity: 0.06 }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || res.statusText)
      }

      const data = await res.json()
      setResult(data)
      onEncoded(receipt, data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const downloadPdf = () => {
    if (!result?.pdf_b64) return
    const link = document.createElement('a')
    link.href = `data:application/pdf;base64,${result.pdf_b64}`
    link.download = `receipt_${form.transaction_id || 'download'}.pdf`
    link.click()
  }

  return (
    <div className="panel">
      <div className="panel-title">01 / Encode</div>

      {/* Store info */}
      <div className="field-row cols-2">
        <div className="field-group">
          <label>Store Name *</label>
          <input
            type="text"
            placeholder="Almond Farm Market"
            value={form.store_name}
            onChange={e => setField('store_name', e.target.value)}
          />
        </div>
        <div className="field-group">
          <label>Date *</label>
          <input
            type="date"
            value={form.date}
            onChange={e => setField('date', e.target.value)}
          />
        </div>
      </div>

      <div className="field-group">
        <label>Store Address</label>
        <input
          type="text"
          placeholder="123 Grove Ln, Sacramento CA 95814"
          value={form.store_address}
          onChange={e => setField('store_address', e.target.value)}
        />
      </div>

      <div className="field-row cols-3">
        <div className="field-group">
          <label>Transaction ID</label>
          <input
            type="text"
            placeholder="TXN-0042"
            value={form.transaction_id}
            onChange={e => setField('transaction_id', e.target.value)}
          />
        </div>
        <div className="field-group">
          <label>Payment Method</label>
          <input
            type="text"
            placeholder="Visa ···· 4242"
            value={form.payment_method}
            onChange={e => setField('payment_method', e.target.value)}
          />
        </div>
        <div className="field-group">
          <label>Cashier</label>
          <input
            type="text"
            placeholder="Jordan"
            value={form.cashier}
            onChange={e => setField('cashier', e.target.value)}
          />
        </div>
      </div>

      {/* Line items */}
      <div style={{ marginBottom: 8 }}>
        <label>Line Items</label>
      </div>
      <table className="items-table">
        <thead>
          <tr>
            <th style={{ width: '38%' }}>Item Name</th>
            <th style={{ width: '12%' }}>Qty</th>
            <th style={{ width: '18%' }}>Unit Price</th>
            <th style={{ width: '14%' }}>Total</th>
            <th style={{ width: '8%' }}></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr key={i}>
              <td>
                <input
                  type="text"
                  placeholder="Item name"
                  value={item.name}
                  onChange={e => updateItem(i, 'name', e.target.value)}
                />
              </td>
              <td>
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={item.qty}
                  onChange={e => updateItem(i, 'qty', parseFloat(e.target.value) || 0)}
                />
              </td>
              <td>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={item.unit_price}
                  onChange={e => updateItem(i, 'unit_price', parseFloat(e.target.value) || 0)}
                />
              </td>
              <td className="col-total">${item.total.toFixed(2)}</td>
              <td>
                {items.length > 1 && (
                  <button className="btn-remove" onClick={() => removeItem(i)}>×</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <button className="btn btn-ghost btn-sm" onClick={addItem} style={{ marginBottom: 14 }}>
        + Add Item
      </button>

      {/* Totals */}
      <div className="totals-strip">
        <div className="total-item">
          <span className="total-label">Subtotal</span>
          <span className="total-value">${subtotal.toFixed(2)}</span>
        </div>
        <div className="total-item">
          <span className="total-label">Tax Rate</span>
          <span className="total-value" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <input
              type="number"
              min="0"
              max="30"
              step="0.25"
              value={form.tax_rate}
              onChange={e => setField('tax_rate', e.target.value)}
              style={{ width: 56, padding: '2px 6px', fontSize: 13, background: 'transparent', border: '1px solid #333' }}
            />
            <span style={{ fontSize: 13, color: 'var(--muted)' }}>%</span>
          </span>
        </div>
        <div className="total-item">
          <span className="total-label">Tax</span>
          <span className="total-value">${taxAmount.toFixed(2)}</span>
        </div>
        <div className="total-item">
          <span className="total-label">Total</span>
          <span className="total-value" style={{ color: 'var(--pink)', fontSize: 18 }}>${total.toFixed(2)}</span>
        </div>
      </div>

      <button
        className="btn btn-primary"
        onClick={handleSubmit}
        disabled={loading || !form.store_name || !form.date}
      >
        {loading ? <><span className="spinner">⟳</span> Encoding…</> : 'Encode & Generate Receipt'}
      </button>

      {error && <div className="error-msg">Error: {error}</div>}

      {result && (
        <div className="result-card">
          <h3>Encode Result</h3>
          {/* /full-flow returns { pdf_b64, texture_b64, analysis } at top level */}
          <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            {result.texture_b64 && (
              <img
                className="texture-preview"
                src={`data:image/png;base64,${result.texture_b64}`}
                alt="Steganographic texture"
                title="Texture PNG — contains encoded receipt data"
              />
            )}
            <div>
              <div className="stat-row" style={{ marginBottom: 14 }}>
                <div className="stat-item">
                  <span className="stat-label">Payload</span>
                  <span className="stat-value accent">
                    {result.analysis?.details?.payload_bytes ?? '—'} bytes
                  </span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Capacity</span>
                  <span className="stat-value">504 bytes</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Texture</span>
                  <span className="stat-value">512×512 px</span>
                </div>
              </div>

              {result.analysis?.summary && (
                <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12, maxWidth: 280 }}>
                  {result.analysis.summary}
                </p>
              )}

              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {result.texture_b64 && (
                  <a
                    href={`data:image/png;base64,${result.texture_b64}`}
                    download="receipt_texture.png"
                    className="btn btn-ghost btn-sm"
                  >
                    ↓ PNG Texture
                  </a>
                )}
                {result.pdf_b64 && (
                  <button className="btn btn-secondary btn-sm" onClick={downloadPdf}>
                    ↓ Download PDF
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
