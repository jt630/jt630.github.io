"""
Steganographic Receipt API — FastAPI application.

Start with:
    uvicorn main:app --reload

Routes
------
POST /encode      EncodeRequest  → EncodeResult
POST /decode      DecodeRequest  → DecodeResult
POST /analyze     AnalysisRequest → AnalysisResult
POST /full-flow   Receipt        → { pdf_b64, texture_b64, analysis }
GET  /health      → { status: "ok", version: "1.0.0" }
"""
from __future__ import annotations

import base64

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
except ImportError as e:
    raise ImportError(
        "FastAPI not installed. Run: pip install fastapi uvicorn"
    ) from e

try:
    from encoder import encode_request, encode
except ImportError as e:
    raise ImportError(
        "encoder module not found. Ensure encoder.py is in the same directory."
    ) from e

try:
    from decoder import decode_request
except ImportError as e:
    raise ImportError(
        "decoder module not found. Ensure decoder.py is in the same directory."
    ) from e

try:
    from receipt import generate_receipt_pdf
except ImportError as e:
    raise ImportError(
        "receipt module not found. Ensure receipt.py is in the same directory."
    ) from e

try:
    from ai_client import analyze_receipt
except ImportError as e:
    raise ImportError(
        "ai_client module not found or missing 'anthropic' package. "
        "Ensure ai_client.py is present and run: pip install anthropic"
    ) from e

from schemas import (
    AnalysisRequest,
    AnalysisResult,
    DecodeRequest,
    DecodeResult,
    EncodeRequest,
    EncodeResult,
    Receipt,
)

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Steganographic Receipt API",
    description=(
        "Encode receipt data invisibly into PNG textures, decode it back, "
        "generate PDFs, and run AI-powered receipt analysis."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Steganographic Receipt API running on http://localhost:8000")


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    """Liveness check."""
    return {"status": "ok", "version": "1.0.0"}


@app.post("/encode", response_model=EncodeResult)
def encode_endpoint(req: EncodeRequest) -> EncodeResult:
    """
    Encode a Receipt into a steganographic PNG texture.

    Returns the texture as base64, plus payload/capacity stats.
    """
    try:
        return encode_request(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Encoding failed: {exc}") from exc


@app.post("/decode", response_model=DecodeResult)
def decode_endpoint(req: DecodeRequest) -> DecodeResult:
    """
    Decode a Receipt from a steganographic PNG texture.

    Accepts a base64-encoded image (any format).
    """
    try:
        return decode_request(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Decoding failed: {exc}") from exc


@app.post("/analyze", response_model=AnalysisResult)
def analyze_endpoint(req: AnalysisRequest) -> AnalysisResult:
    """
    Analyse a Receipt with Claude AI.

    mode: "expense" | "split" | "warranty" | "returns"
    """
    try:
        return analyze_receipt(req.receipt, mode=req.mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc


@app.post("/full-flow")
def full_flow_endpoint(receipt: Receipt) -> dict:
    """
    The killer endpoint: one Receipt in, everything out.

    1. Encodes receipt data into a steganographic PNG texture.
    2. Generates a PDF receipt.
    3. Runs expense analysis via Claude AI.

    Returns:
        pdf_b64      : base64-encoded PDF bytes
        texture_b64  : base64-encoded PNG texture bytes
        analysis     : AnalysisResult dict
    """
    # Step 1 — steganographic texture
    try:
        png_bytes, _payload_len, _cap = encode(receipt)
        texture_b64 = base64.b64encode(png_bytes).decode()
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"Texture encoding failed: {exc}"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Texture encoding error: {exc}"
        ) from exc

    # Step 2 — PDF generation (uses the same texture PNG from step 1)
    try:
        pdf_bytes = generate_receipt_pdf(receipt, png_bytes)
        pdf_b64 = base64.b64encode(pdf_bytes).decode()
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"PDF generation failed: {exc}"
        ) from exc

    # Step 3 — AI analysis (expense mode for the full-flow)
    try:
        analysis = analyze_receipt(receipt, mode="expense")
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"AI analysis failed: {exc}"
        ) from exc

    return {
        "pdf_b64": pdf_b64,
        "texture_b64": texture_b64,
        "analysis": analysis.model_dump(),
    }
