"""
Stego — shared schemas for the image steganography analyzer.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class FormatInfo(BaseModel):
    format: str                        # "JPEG" | "PNG" | "GIF" | "WEBP"
    lossless: bool
    width: int
    height: int
    channels: int
    mode: str                          # "RGB" | "RGBA" | "L" etc.
    estimated_quality: Optional[int] = None   # JPEG q-factor, None if N/A
    estimated_recompressions: int = 0  # 0 = fresh, 1+ = processed
    file_size_bytes: int = 0


class TestResult(BaseModel):
    name: str
    slug: str                          # machine key for frontend
    verdict: str                       # "CLEAN" | "SUSPICIOUS" | "DETECTED" | "SKIPPED"
    score: float = Field(ge=0.0, le=1.0)  # 0=clean, 1=definitely stego
    detail: str                        # human-readable explanation
    data: dict = Field(default_factory=dict)  # extra data for frontend (charts etc)


class AnalysisReport(BaseModel):
    image_hash: str                    # SHA-256 of raw uploaded bytes
    format: FormatInfo
    tests: list[TestResult]
    verdict: str                       # "CLEAN" | "SUSPICIOUS" | "PAYLOAD_DETECTED"
    confidence: float = Field(ge=0.0, le=1.0)
    payload_detected: bool = False
    payload_scheme: Optional[str] = None
    payload_size_bytes: Optional[int] = None
    payload_preview: Optional[str] = None   # first 200 chars if text-like


class AnalyzeRequest(BaseModel):
    image_b64: str                     # base64-encoded image (any format)
    filename: Optional[str] = None


class RevealRequest(BaseModel):
    image_b64: str
    scheme: str                        # which scheme to attempt full decode
