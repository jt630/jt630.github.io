#!/usr/bin/env python3
"""
encode_prank.py — LSB-encode a secret message into any PNG/JPG image.

Usage:
    python encode_prank.py <input_image> [output.png] [-m "your message"]
    python encode_prank.py <input_image> --decode

Examples:
    python encode_prank.py photo.jpg
    python encode_prank.py photo.jpg out.png -m "you've been had"
    python encode_prank.py out.png --decode

Requirements: Pillow, numpy
    pip install pillow numpy
"""
import io
import struct
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("Install deps first:  pip install pillow numpy")

# ── The secret message ────────────────────────────────────────────────────────

MESSAGE = """Oi Josh, you absolute muppet — this image has been secretly compromised, much like your mum has been compromised by half of Shepherd's Bush. This is Billy Butcher speaking from beyond the pixels. Tell your mum I said cheers."""

# ── LSB encoder ──────────────────────────────────────────────────────────────

MAGIC = b"STEG"


def lsb_encode(img_bytes: bytes, message: str) -> bytes:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    arr = np.array(img, dtype=np.uint8).copy()
    flat = arr.flatten()

    payload = message.encode("utf-8")
    frame = MAGIC + struct.pack(">I", len(payload)) + payload
    bits = [(byte >> i) & 1 for byte in frame for i in range(7, -1, -1)]

    capacity = len(flat)
    needed = len(bits)
    if needed > capacity:
        sys.exit(f"Image too small ({capacity} pixels) for message ({needed} bits needed). Use a larger image.")

    for i, bit in enumerate(bits):
        flat[i] = (flat[i] & 0xFE) | bit

    result = Image.fromarray(flat.reshape(arr.shape), "RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()


def lsb_decode(img_bytes: bytes) -> str | None:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    flat = arr.flatten()

    def read_bytes(start_bit: int, n: int) -> bytes:
        out = bytearray()
        for i in range(n):
            byte = 0
            for j in range(8):
                idx = start_bit + i * 8 + j
                if idx >= len(flat):
                    return bytes(out)
                byte = (byte << 1) | int(flat[idx] & 1)
            out.append(byte)
        return bytes(out)

    magic = read_bytes(0, 4)
    if magic != MAGIC:
        return None
    length = struct.unpack(">I", read_bytes(32, 4))[0]
    payload = read_bytes(64, length)
    return payload.decode("utf-8", errors="replace")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__)
        sys.exit(1)

    # -m "message" flag
    message = MESSAGE
    if "-m" in sys.argv:
        idx = sys.argv.index("-m")
        if idx + 1 >= len(sys.argv):
            sys.exit("Usage: -m \"your message\"")
        message = sys.argv[idx + 1]

    src = Path(args[0])
    if not src.exists():
        sys.exit(f"File not found: {src}")

    dst = Path(args[1]) if len(args) > 1 else src.with_stem(src.stem + "_encoded").with_suffix(".png")

    print(f"Reading  {src}")
    img_bytes = src.read_bytes()

    print(f"Encoding message ({len(message)} chars)…")
    encoded = lsb_encode(img_bytes, message)

    dst.write_bytes(encoded)
    print(f"Saved →  {dst}  ({len(encoded) // 1024}KB)")

    decoded = lsb_decode(encoded)
    if decoded == message:
        print("Verify ✓  message decodes correctly")
    else:
        print("WARNING: decode mismatch — check the image")

    print()
    print("Decode with:  python encode_prank.py <image> --decode")
    print("           or drop it on https://almondfarm.us/brain/stego")
    print()
    print(f"Message: {message[:80]}{'…' if len(message) > 80 else ''}")


if __name__ == "__main__":
    # Handle --decode mode
    if "--decode" in sys.argv:
        args = [a for a in sys.argv[1:] if a != "--decode"]
        if not args:
            sys.exit("Usage: python encode_prank.py <image> --decode")
        img_bytes = Path(args[0]).read_bytes()
        msg = lsb_decode(img_bytes)
        if msg:
            print(f"Decoded message:\n\n{msg}")
        else:
            print("No STEG message found in this image.")
    else:
        main()
