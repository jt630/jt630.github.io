import { useState, useRef, useEffect } from 'react'

const API = 'http://localhost:8000'

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      // strip the data:...;base64, prefix
      const b64 = reader.result.split(',')[1]
      resolve(b64)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

function ReceiptDisplay({ receipt }) {
  if (!receipt) return null
  return (
    <div>
      <div className="receipt-meta">
        <span className="key">Store</span>
        <span className="val">{receipt.store_name}</span>
        {receipt.store_address && <>
          <span className="key">Address</span>
          <span className="val">{receipt.store_address}</span>
        </>}
        <span className="key">Date</span>
        <span className="val">{receipt.date}</span>
        {receipt.transaction_id && <>
          <span className="key">Txn ID</span>
          <span className="val">{receipt.transaction_id}</span>
        </>}
        {receipt.payment_method && <>
          <span className="key">Payment</span>
          <span className="val">{receipt.payment_method}</span>
        </>}
        {receipt.cashier && <>
          <span className="key">Cashier</span>
          <span className="val">{receipt.cashier}</span>
        </>}
      </div>

      {receipt.items && receipt.items.length > 0 && (
        <table className="receipt-table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Qty</th>
              <th>Unit $</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {receipt.items.map((item, i) => (
              <tr key={i}>
                <td>{item.name}</td>
                <td style={{ fontFamily: 'var(--mono)' }}>{item.qty}</td>
                <td style={{ fontFamily: 'var(--mono)' }}>${item.unit_price.toFixed(2)}</td>
                <td style={{ fontFamily: 'var(--mono)', color: 'var(--gold)' }}>${item.total.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan="3" style={{ paddingTop: 8, color: 'var(--muted)', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1 }}>Subtotal</td>
              <td style={{ fontFamily: 'var(--mono)', paddingTop: 8 }}>${receipt.subtotal?.toFixed(2)}</td>
            </tr>
            {receipt.tax_amount != null && (
              <tr>
                <td colSpan="3" style={{ color: 'var(--muted)', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1 }}>Tax</td>
                <td style={{ fontFamily: 'var(--mono)' }}>${receipt.tax_amount?.toFixed(2)}</td>
              </tr>
            )}
            <tr>
              <td colSpan="3" style={{ color: 'var(--pink)', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 700 }}>Total</td>
              <td style={{ fontFamily: 'var(--mono)', color: 'var(--pink)', fontWeight: 700, fontSize: 15 }}>${receipt.total?.toFixed(2)}</td>
            </tr>
          </tfoot>
        </table>
      )}
    </div>
  )
}

export default function DecodePanel({ onDecoded }) {
  const [imageB64, setImageB64] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  // Camera
  const [cameraActive, setCameraActive] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)

  // ── File input ─────────────────────────────────────────────────
  const handleFile = async (file) => {
    if (!file) return
    setError(null)
    setResult(null)
    try {
      const b64 = await fileToBase64(file)
      setImageB64(b64)
      setPreviewUrl(URL.createObjectURL(file))
    } catch (e) {
      setError('Failed to read file: ' + e.message)
    }
  }

  const onFileChange = (e) => handleFile(e.target.files[0])

  const onDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    handleFile(e.dataTransfer.files[0])
  }

  // ── Camera ─────────────────────────────────────────────────────
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        videoRef.current.play()
      }
      setCameraActive(true)
      setError(null)
    } catch (e) {
      setError('Camera access denied: ' + e.message)
    }
  }

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
    setCameraActive(false)
  }

  const captureSnapshot = () => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas) return
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0)
    const dataUrl = canvas.toDataURL('image/png')
    const b64 = dataUrl.split(',')[1]
    setImageB64(b64)
    setPreviewUrl(dataUrl)
    stopCamera()
    setResult(null)
    setError(null)
  }

  // Stop stream on unmount
  useEffect(() => () => stopCamera(), [])

  // ── Decode ─────────────────────────────────────────────────────
  const handleDecode = async () => {
    if (!imageB64) return
    setError(null)
    setLoading(true)

    try {
      const res = await fetch(`${API}/decode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_b64: imageB64, texture_size: 512 }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || res.statusText)
      }

      const data = await res.json()
      setResult(data)
      onDecoded(data.receipt, data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel">
      <div className="panel-title">02 / Decode</div>

      {/* Camera controls */}
      <div className="camera-section">
        <div className="camera-btn-row">
          {!cameraActive ? (
            <button className="btn btn-ghost btn-sm" onClick={startCamera}>
              📷 Use Camera
            </button>
          ) : (
            <>
              <button className="btn btn-primary btn-sm" onClick={captureSnapshot}>
                Capture
              </button>
              <button className="btn btn-ghost btn-sm" onClick={stopCamera}>
                Cancel
              </button>
            </>
          )}
        </div>

        {cameraActive && (
          <video ref={videoRef} className="camera-feed" muted playsInline />
        )}
        <canvas ref={canvasRef} className="camera-canvas" />
      </div>

      {/* File upload */}
      {!cameraActive && (
        <div
          className={`upload-zone${dragOver ? ' drag-over' : ''}`}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
        >
          <input type="file" accept="image/*" onChange={onFileChange} />
          {previewUrl ? (
            <img src={previewUrl} alt="Selected" className="upload-preview" />
          ) : (
            <p className="upload-text">
              <strong>Click to select</strong> or drag an image here
              <br />
              <span style={{ fontSize: 11, marginTop: 4, display: 'block' }}>PNG, JPG, WEBP — any steganographic texture</span>
            </p>
          )}
        </div>
      )}

      {previewUrl && !cameraActive && (
        <img src={previewUrl} alt="Preview" className="upload-preview" style={{ marginBottom: 12 }} />
      )}

      <button
        className="btn btn-primary"
        onClick={handleDecode}
        disabled={loading || !imageB64}
      >
        {loading ? <><span className="spinner">⟳</span> Decoding…</> : 'Decode'}
      </button>

      {error && <div className="error-msg">Error: {error}</div>}

      {result && (
        <div className="result-card">
          <h3>Decoded Receipt</h3>

          <div className="stat-row" style={{ marginBottom: 12 }}>
            <div className="stat-item">
              <span className="stat-label">Confidence</span>
              <span className="stat-value accent">{(result.confidence * 100).toFixed(1)}%</span>
              <div className="confidence-bar-track" style={{ width: 120 }}>
                <div
                  className="confidence-bar-fill"
                  style={{ width: `${result.confidence * 100}%` }}
                />
              </div>
            </div>
            <div className="stat-item">
              <span className="stat-label">CRC</span>
              <span className={`badge ${result.crc_ok ? 'badge-ok' : 'badge-err'}`}>
                {result.crc_ok ? 'PASS' : 'FAIL'}
              </span>
            </div>
          </div>

          <hr className="divider" />
          <ReceiptDisplay receipt={result.receipt} />
        </div>
      )}
    </div>
  )
}
