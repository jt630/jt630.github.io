"""
Steganographic receipt texture encoder.

Algorithm
─────────
1. Serialise Receipt → JSON → zlib-compress → payload bytes
2. Frame the payload:
       [MAGIC 2B][LENGTH 2B LE][PAYLOAD][CRC32 4B]
3. Convert frame to a bitstream
4. Generate a 512×512 (or custom size) grayscale noise carrier image
5. For each 8×8 block in raster order:
       bit=1 → add  DELTA to every pixel in the block (clamp 0-255)
       bit=0 → sub  DELTA from every pixel               (clamp 0-255)
6. Convert to RGBA, set A = round(opacity × 255), return as PNG bytes

Block layout (512×512, 8px blocks → 64×64 = 4096 blocks = 512 bytes):
  capacity_bits  = (size // BLOCK_SIZE) ** 2
  capacity_bytes = capacity_bits // 8
  max_payload    = capacity_bytes − 2 (magic) − 2 (length) − 4 (crc)
                 = 512 − 8 = 504 bytes (compressed JSON easily fits)
"""
from __future__ import annotations

import io
import json
import struct
import zlib
from typing import Union

import numpy as np
from PIL import Image

from schemas import (
    BLOCK_SIZE, MAGIC, DELTA, BASE_GRAY, NOISE_AMP,
    EncodeRequest, EncodeResult, Receipt,
)
import base64


# ── helpers ─────────────────────────────────────────────────────────────────

def _receipt_to_payload(receipt: Receipt) -> bytes:
    """JSON-serialise then zlib-compress a Receipt."""
    raw = json.dumps(receipt.model_dump(exclude_none=True), separators=(",", ":")).encode()
    return zlib.compress(raw, level=9)


def _build_frame(payload: bytes) -> bytes:
    """Wrap payload in [MAGIC][uint16-len][payload][crc32]."""
    length = struct.pack("<H", len(payload))
    crc = struct.pack("<I", zlib.crc32(payload) & 0xFFFFFFFF)
    return MAGIC + length + payload + crc


def _frame_to_bits(frame: bytes) -> list[int]:
    bits: list[int] = []
    for byte in frame:
        for shift in range(7, -1, -1):   # MSB first
            bits.append((byte >> shift) & 1)
    return bits


def _capacity(size: int) -> int:
    """Total bit capacity for a square texture of *size* pixels."""
    blocks = (size // BLOCK_SIZE) ** 2
    return blocks  # one bit per block


def capacity_bytes(size: int = 512) -> int:
    """Human-friendly: max payload bytes (after framing overhead)."""
    return _capacity(size) // 8 - len(MAGIC) - 2 - 4  # magic + length + crc


# ── carrier texture ──────────────────────────────────────────────────────────

def _make_carrier(size: int, rng: np.random.Generator) -> np.ndarray:
    """
    512×512 (or custom) uint8 grayscale array that looks like paper grain.
    Values clustered around BASE_GRAY ± NOISE_AMP.
    """
    noise = rng.integers(
        low=BASE_GRAY - NOISE_AMP,
        high=BASE_GRAY + NOISE_AMP + 1,
        size=(size, size),
        dtype=np.int32,
    )
    return np.clip(noise, 0, 255).astype(np.uint8)


# ── encoding ─────────────────────────────────────────────────────────────────

def encode(
    receipt: Receipt,
    texture_size: int = 512,
    opacity: float = 0.06,
    seed: int = 42,
) -> tuple[bytes, int, int]:
    """
    Encode *receipt* into a grayscale PNG texture.

    Returns
    -------
    png_bytes   : raw PNG file bytes (RGBA, with alpha = opacity channel)
    payload_len : compressed payload length in bytes
    cap         : capacity in bytes for this texture size
    """
    rng = np.random.default_rng(seed)
    payload = _receipt_to_payload(receipt)
    frame = _build_frame(payload)
    bits = _frame_to_bits(frame)

    cap_bits = _capacity(texture_size)
    if len(bits) > cap_bits:
        raise ValueError(
            f"Payload too large: {len(bits)} bits required, "
            f"only {cap_bits} available (texture_size={texture_size}). "
            f"Try a larger texture or shorter receipt."
        )

    carrier = _make_carrier(texture_size, rng).astype(np.int32)
    blocks_per_row = texture_size // BLOCK_SIZE

    for idx, bit in enumerate(bits):
        row = idx // blocks_per_row
        col = idx % blocks_per_row
        r0, c0 = row * BLOCK_SIZE, col * BLOCK_SIZE
        delta = DELTA if bit == 1 else -DELTA
        carrier[r0:r0 + BLOCK_SIZE, c0:c0 + BLOCK_SIZE] += delta

    carrier = np.clip(carrier, 0, 255).astype(np.uint8)

    # Convert to RGBA with controlled opacity
    alpha = int(round(opacity * 255))
    rgba = np.zeros((texture_size, texture_size, 4), dtype=np.uint8)
    rgba[:, :, 0] = carrier
    rgba[:, :, 1] = carrier
    rgba[:, :, 2] = carrier
    rgba[:, :, 3] = alpha

    img = Image.fromarray(rgba, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False, compress_level=1)
    return buf.getvalue(), len(payload), capacity_bytes(texture_size)


# ── public API ───────────────────────────────────────────────────────────────

def encode_request(req: EncodeRequest) -> EncodeResult:
    png_bytes, payload_len, cap = encode(
        receipt=req.receipt,
        texture_size=req.texture_size,
        opacity=req.opacity,
    )
    return EncodeResult(
        texture_b64=base64.b64encode(png_bytes).decode(),
        payload_bytes=payload_len,
        capacity_bytes=cap,
        texture_size=req.texture_size,
    )


# ── CLI smoke test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    from schemas import LineItem

    sample = Receipt(
        store_name="Almond Farm Market",
        store_address="123 Grove Ln, Sacramento CA 95814",
        date="2026-04-14",
        transaction_id="TXN-0042",
        items=[
            LineItem(name="Raw Almonds 1lb",   sku="ALM-001", qty=2, unit_price=12.99, total=25.98),
            LineItem(name="Local Honey 12oz",  sku="HON-003", qty=1, unit_price=8.49,  total=8.49),
            LineItem(name="Olive Oil 500ml",   sku="OIL-007", qty=1, unit_price=14.99, total=14.99),
        ],
        subtotal=49.46,
        tax_rate=0.0875,
        tax_amount=4.33,
        total=53.79,
        payment_method="Visa •••• 4242",
        cashier="Jordan",
    )

    png, plen, cap = encode(sample)
    print(f"Encoded {plen} compressed bytes into texture (capacity: {cap} bytes)")
    print(f"PNG size: {len(png):,} bytes")
    with open("/tmp/receipt_texture.png", "wb") as f:
        f.write(png)
    print("Saved to /tmp/receipt_texture.png")
