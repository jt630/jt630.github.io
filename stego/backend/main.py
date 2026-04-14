"""
Stego API — FastAPI application.

Start with:
    uvicorn main:app --reload --port 8001

Routes
------
POST /analyze   AnalyzeRequest → AnalysisReport
GET  /health    → { status: "ok" }
"""
from __future__ import annotations
import base64
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from analyzer import analyze
from schemas import AnalysisReport, AnalyzeRequest

app = FastAPI(title="Stego", description="Image steganography analyzer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}


@app.post("/analyze", response_model=AnalysisReport)
def analyze_endpoint(req: AnalyzeRequest) -> AnalysisReport:
    try:
        image_bytes = base64.b64decode(req.image_b64)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid base64 image data.")
    try:
        return analyze(image_bytes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")
