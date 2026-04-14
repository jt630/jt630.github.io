"""
Shared Pydantic schemas for the Steganographic Receipt System.
All modules import from here — never define models elsewhere.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ── Receipt data model ──────────────────────────────────────────────────────

class LineItem(BaseModel):
    name: str
    sku: Optional[str] = None
    qty: float = 1.0
    unit_price: float
    total: float


class Receipt(BaseModel):
    store_name: str
    store_address: Optional[str] = None
    date: str                          # ISO 8601: "2026-04-14"
    transaction_id: Optional[str] = None
    items: list[LineItem] = Field(default_factory=list)
    subtotal: float
    tax_rate: Optional[float] = None   # e.g. 0.0875 for 8.75%
    tax_amount: float
    total: float
    payment_method: Optional[str] = None
    cashier: Optional[str] = None


# ── Encode / decode wire types ──────────────────────────────────────────────

class EncodeRequest(BaseModel):
    receipt: Receipt
    texture_size: int = 512            # must be multiple of BLOCK_SIZE (8)
    opacity: float = Field(0.06, ge=0.01, le=0.30)


class EncodeResult(BaseModel):
    texture_b64: str                   # base64-encoded PNG
    payload_bytes: int
    capacity_bytes: int
    texture_size: int


class DecodeRequest(BaseModel):
    image_b64: str                     # base64-encoded image (any format)
    texture_size: int = 512            # expected texture grid, passed from encoder


class DecodeResult(BaseModel):
    receipt: Receipt
    confidence: float = Field(ge=0.0, le=1.0)
    crc_ok: bool


# ── AI analysis types ───────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    receipt: Receipt
    mode: str = "expense"              # "expense" | "split" | "warranty" | "returns"


class AnalysisResult(BaseModel):
    mode: str
    summary: str
    details: dict
    raw_response: str


# ── Encoding constants (imported by both encoder and decoder) ───────────────

BLOCK_SIZE: int = 8          # pixels per block edge
MAGIC: bytes = b"\xAF\x01"  # 2-byte magic number (AlmondFarm v1)
DELTA: int = 14              # brightness delta: +DELTA for bit=1, -DELTA for bit=0
BASE_GRAY: int = 128         # carrier texture base grey level
NOISE_AMP: int = 8           # ±noise amplitude on carrier (visual grain)
