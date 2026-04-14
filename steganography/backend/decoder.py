"""
Steganographic receipt texture decoder.

Algorithm
─────────
1. Open image, convert to grayscale, resize to texture_size × texture_size
2. Cast to float32 numpy array
3. For each of the four 90° orientations [0°, 90°, 180°, 270°]:
   a. Divide the image into BLOCK_SIZE × BLOCK_SIZE pixel blocks
   b. Compute the mean value of each block
   c. Threshold: mean > BASE_GRAY → bit=1, else bit=0
   d. Pack bits into bytes (MSB first within each byte)
   e. Check first 2 bytes against MAGIC
   f. If magic matches: read LENGTH (uint16-LE), extract PAYLOAD + CRC32
   g. Verify CRC32; if good, zlib-decompress → JSON → Receipt
   h. Compute confidence = fraction of blocks where |mean − BASE_GRAY| > DELTA*0.5
4. Return (receipt, confidence, crc_ok) for the first orientation that passes CRC,
   or raise ValueError if no orientation succeeds.

Frame layout (matches encoder exactly):
    [MAGIC 2B = 0xAF 0x01][LENGTH 2B little-endian][PAYLOAD bytes][CRC32 4B LE]

Registration / rotation detection
──────────────────────────────────
`find_registration_corner` is a lightweight heuristic: it inspects the average
brightness of each quadrant and compares against what the encoder actually writes.
Because we just try all four np.rot90 rotations it is not strictly required for
decoding, but it is exported so callers can surface a "likely rotation" hint.
"""
from __future__ import annotations

import base64
import io
import json
import struct
import zlib
from typing import Optional

import numpy as np
from PIL import Image

from schemas import (
    BASE_GRAY, BLOCK_SIZE, DELTA, MAGIC,
    DecodeRequest, DecodeResult, Receipt,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _to_grayscale_array(image_bytes: bytes, texture_size: int) -> np.ndarray:
    """
    Open *image_bytes* (any format Pillow understands), convert to grayscale,
    resize to *texture_size* × *texture_size*, return float32 ndarray.
    """
    img = Image.open(io.BytesIO(image_bytes))
    # RGBA textures produced by the encoder: convert through grayscale.
    # For RGBA the L channel is derived from the RGB channels, not alpha.
    img = img.convert("L")
    if img.size != (texture_size, texture_size):
        img = img.resize((texture_size, texture_size), Image.LANCZOS)
    return np.asarray(img, dtype=np.float32)


def _read_blocks(gray: np.ndarray) -> np.ndarray:
    """
    Given a *texture_size* × *texture_size* float32 grayscale array, return a
    1-D float32 array of per-block averages in raster order (row-major).
    """
    size = gray.shape[0]
    blocks_per_edge = size // BLOCK_SIZE
    # Reshape into a 2-D grid of blocks and take mean of each
    # gray shape: (H, W) → (blocks_per_edge, BLOCK_SIZE, blocks_per_edge, BLOCK_SIZE)
    reshaped = gray.reshape(
        blocks_per_edge, BLOCK_SIZE,
        blocks_per_edge, BLOCK_SIZE,
    )
    # Average over the two block-interior axes (axis 1 and 3)
    block_means = reshaped.mean(axis=(1, 3))          # shape: (bpe, bpe)
    return block_means.ravel()                         # shape: (bpe*bpe,)


def _bits_to_bytes(bits: np.ndarray) -> bytes:
    """
    Pack a bit array (MSB first, same convention as the encoder) into bytes.
    Truncates to a whole number of bytes; excess bits are dropped.
    """
    n_bytes = len(bits) // 8
    result = bytearray(n_bytes)
    for i in range(n_bytes):
        byte_bits = bits[i * 8 : i * 8 + 8]
        val = 0
        for shift, b in enumerate(byte_bits):
            val |= int(b) << (7 - shift)
        result[i] = val
    return bytes(result)


def _confidence(block_means: np.ndarray) -> float:
    """
    Fraction of blocks whose average deviates from BASE_GRAY by more than
    DELTA * 0.5 — i.e., blocks that are "clearly" encoded rather than ambiguous.
    """
    half_delta = DELTA * 0.5
    clear = np.sum(np.abs(block_means - BASE_GRAY) > half_delta)
    return float(clear) / float(len(block_means))


def _try_decode(
    gray: np.ndarray,
) -> Optional[tuple[Receipt, float, bool]]:
    """
    Attempt to decode a single orientation of *gray*.

    Returns (receipt, confidence, crc_ok) if the magic bytes match **and**
    the CRC passes; returns None if magic is wrong or the data is corrupt.
    """
    block_means = _read_blocks(gray)
    bits = (block_means > BASE_GRAY).astype(np.uint8)
    data = _bits_to_bytes(bits)

    # ── check magic ──────────────────────────────────────────────────────────
    if len(data) < 2 or data[:2] != MAGIC:
        return None

    # ── extract length ────────────────────────────────────────────────────────
    if len(data) < 4:
        return None
    (payload_len,) = struct.unpack_from("<H", data, 2)

    # ── extract payload + CRC ─────────────────────────────────────────────────
    payload_start = 4                              # after MAGIC(2) + LENGTH(2)
    payload_end = payload_start + payload_len
    crc_end = payload_end + 4

    if len(data) < crc_end:
        return None

    payload = data[payload_start:payload_end]
    (stored_crc,) = struct.unpack_from("<I", data, payload_end)
    computed_crc = zlib.crc32(payload) & 0xFFFFFFFF
    crc_ok = (stored_crc == computed_crc)

    if not crc_ok:
        return None

    # ── decompress → JSON → Receipt ───────────────────────────────────────────
    raw_json = zlib.decompress(payload)
    receipt = Receipt.model_validate(json.loads(raw_json))

    conf = _confidence(block_means)
    return receipt, conf, crc_ok


# ── rotation heuristic (exported for callers) ─────────────────────────────────

def find_registration_corner(gray: np.ndarray) -> int:
    """
    Lightweight heuristic to guess which 90° rotation would bring the image
    into the encoder's original orientation.

    Inspects per-quadrant mean brightness.  Because real prints may have
    variable lighting this is best-effort; the full decode() always tries all
    four orientations regardless.

    Returns the *k* value for ``np.rot90(gray, k)`` that is most likely
    correct (0, 1, 2, or 3).

    Strategy: the top-left 8×8 block encodes the MSB of the first MAGIC byte
    (0xAF = 1010_1111).  Its MSB is 1, so the first block should be bright
    (mean > BASE_GRAY).  We check each of the four potential "first block"
    corners.
    """
    h, w = gray.shape
    bs = BLOCK_SIZE
    corners = [
        gray[:bs, :bs].mean(),           # top-left  → k=0
        gray[:bs, w-bs:].mean(),         # top-right → k=1 (rot90 once)
        gray[h-bs:, w-bs:].mean(),       # bot-right → k=2
        gray[h-bs:, :bs].mean(),         # bot-left  → k=3
    ]
    # First bit of MAGIC[0]=0xAF is 1 → first block should be bright
    # Pick the corner that is most above BASE_GRAY
    best_k = int(np.argmax([c - BASE_GRAY for c in corners]))
    return best_k


# ── public API ─────────────────────────────────────────────────────────────────

def decode(image_bytes: bytes, texture_size: int = 512) -> tuple[Receipt, float, bool]:
    """
    Decode a receipt from a steganographic texture image.

    Parameters
    ----------
    image_bytes : bytes
        Raw image file bytes (PNG, JPEG, or any format Pillow can open).
    texture_size : int
        Expected grid size in pixels (default 512).  Must match the value
        used during encoding.

    Returns
    -------
    receipt    : Receipt
    confidence : float in [0, 1] — fraction of "clearly" encoded blocks
    crc_ok     : bool — always True on the returned result (False raises)

    Raises
    ------
    ValueError
        If no orientation yields valid MAGIC + CRC.
    """
    gray = _to_grayscale_array(image_bytes, texture_size)

    for k in range(4):
        rotated = np.rot90(gray, k=k)
        result = _try_decode(rotated)
        if result is not None:
            return result

    raise ValueError(
        "Could not decode receipt: MAGIC bytes not found in any of the four "
        "90° orientations.  The image may not be a steganographic texture, "
        "or the texture_size parameter may not match the encoder setting."
    )


def decode_request(req: DecodeRequest) -> DecodeResult:
    """
    Decode from a :class:`DecodeRequest` (base64-encoded image).

    Returns a :class:`DecodeResult`.
    """
    image_bytes = base64.b64decode(req.image_b64)
    receipt, confidence, crc_ok = decode(image_bytes, texture_size=req.texture_size)
    return DecodeResult(
        receipt=receipt,
        confidence=round(confidence, 4),
        crc_ok=crc_ok,
    )


# ── CLI smoke test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    path = "/tmp/receipt_texture.png"
    print(f"Decoding {path} …")
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        receipt, confidence, crc_ok = decode(raw)
    except FileNotFoundError:
        print(f"ERROR: {path} not found.  Run encoder.py first.", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"CRC OK     : {crc_ok}")
    print(f"Confidence : {confidence:.2%}")
    print(f"Receipt    :")
    print(receipt.model_dump_json(indent=2))
