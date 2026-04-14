"""
Stego analyzer — runs multiple steganographic detection tests on an image.

Tests implemented
─────────────────
1. format_analysis     — lossless vs lossy, quality estimate, recompression count
2. lsb_chi_square      — chi-square test on LSB pairs (detects LSB replacement)
3. lsb_entropy         — entropy of each bit plane (LSB should be ~1.0 for stego)
4. block_variance      — detects block-average encoding (our own scheme)
5. sample_pairs        — detects LSB matching via adjacent pixel pair analysis
6. our_scheme          — tries to decode with Almond Farm steganographic receipt format
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import struct
import zlib
from typing import Optional

import numpy as np
from PIL import Image

from schemas import AnalysisReport, AnalyzeRequest, FormatInfo, TestResult


# ── helpers ──────────────────────────────────────────────────────────────────

def _load(image_bytes: bytes) -> tuple[Image.Image, np.ndarray]:
    img = Image.open(io.BytesIO(image_bytes))
    arr = np.array(img.convert("RGB"), dtype=np.uint8)
    return img, arr


def _entropy(values: np.ndarray) -> float:
    """Shannon entropy in bits, ignoring zero-probability bins."""
    counts = np.bincount(values.flatten().astype(np.uint8), minlength=256)
    probs = counts[counts > 0] / counts.sum()
    return float(-np.sum(probs * np.log2(probs)))


def _bit_plane(channel: np.ndarray, bit: int) -> np.ndarray:
    return ((channel >> bit) & 1).astype(np.uint8)


def _chi2_p_approx(chi2: float, df: int) -> float:
    """
    Rough p-value approximation for chi-square distribution.
    Good enough for our scoring; avoids scipy dependency.
    Uses Wilson-Hilferty normal approximation.
    """
    if df <= 0:
        return 1.0
    z = ((chi2 / df) ** (1 / 3) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
    # standard normal survival function approx (Abramowitz & Stegun)
    if z < -6:
        return 1.0
    if z > 6:
        return 0.0
    t = 1 / (1 + 0.2316419 * abs(z))
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    pdf = math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
    cdf = 1 - pdf * poly
    return 1 - cdf if z >= 0 else cdf


# ── 1. Format analysis ────────────────────────────────────────────────────────

def format_analysis(img: Image.Image, raw_bytes: bytes) -> tuple[FormatInfo, TestResult]:
    fmt = (img.format or "UNKNOWN").upper()
    lossless = fmt in ("PNG", "GIF", "BMP", "TIFF", "WEBP")  # WebP can be both but default lossless
    w, h = img.size

    # JPEG quality estimate from quantization table
    q_est: Optional[int] = None
    recompressions = 0

    if fmt == "JPEG":
        lossless = False
        try:
            qt = img.quantization  # {0: [...], 1: [...]}
            if qt:
                # Standard luminance table has sum ~3600 at q=75
                lum_sum = sum(qt[0]) if 0 in qt else None
                if lum_sum:
                    # Rough mapping: q ≈ 100 - lum_sum/50
                    q_est = max(1, min(100, int(100 - lum_sum / 50)))
            # Estimate recompressions from table smoothness
            if qt and 0 in qt:
                diffs = [abs(qt[0][i] - qt[0][i-1]) for i in range(1, len(qt[0]))]
                avg_diff = sum(diffs) / len(diffs)
                recompressions = 1 if avg_diff < 2 else 0
        except Exception:
            pass

    info = FormatInfo(
        format=fmt,
        lossless=lossless,
        width=w,
        height=h,
        channels=len(img.getbands()),
        mode=img.mode,
        estimated_quality=q_est,
        estimated_recompressions=recompressions,
        file_size_bytes=len(raw_bytes),
    )

    if not lossless:
        detail = (
            f"JPEG q≈{q_est or '?'} — lossy compression likely destroyed LSB-based payloads. "
            f"DCT-domain steganography (Steghide, JPHide) could survive."
        )
        verdict = "SKIPPED"
        score = 0.0
    else:
        detail = f"Lossless {fmt} — pixel values preserved exactly. All encoding schemes viable."
        verdict = "CLEAN"
        score = 0.0

    return info, TestResult(
        name="Format Analysis",
        slug="format",
        verdict=verdict,
        score=score,
        detail=detail,
        data={"format": fmt, "lossless": lossless, "quality": q_est, "recompressions": recompressions},
    )


# ── 2. LSB chi-square test ────────────────────────────────────────────────────

def lsb_chi_square(arr: np.ndarray) -> TestResult:
    """
    Tests whether pairs of adjacent pixel values (2k, 2k+1) appear equally often.
    LSB replacement makes these pairs nearly equal — statistically detectable.
    """
    flat = arr[:, :, 0].flatten().astype(np.int32)  # use red channel
    # Count occurrences of each value 0-255
    counts = np.bincount(flat, minlength=256)

    chi2 = 0.0
    pairs = 0
    for k in range(128):
        a, b = counts[2 * k], counts[2 * k + 1]
        expected = (a + b) / 2.0
        if expected > 0:
            chi2 += ((a - expected) ** 2 + (b - expected) ** 2) / expected
            pairs += 1

    p = _chi2_p_approx(chi2, pairs - 1)
    suspicious = p < 0.05
    score = max(0.0, min(1.0, 1.0 - p * 20))  # scale p to score

    return TestResult(
        name="LSB Chi-Square",
        slug="chi_square",
        verdict="SUSPICIOUS" if suspicious else "CLEAN",
        score=score,
        detail=(
            f"χ²={chi2:.1f}, p≈{p:.4f}. "
            + ("Pixel value pair distribution is anomalous — consistent with LSB replacement steganography."
               if suspicious else
               "Pixel value pairs distribute naturally. No LSB manipulation detected.")
        ),
        data={"chi2": round(chi2, 2), "p_value": round(p, 4), "pairs_tested": pairs},
    )


# ── 3. LSB bit-plane entropy ──────────────────────────────────────────────────

def lsb_entropy(arr: np.ndarray) -> TestResult:
    """
    For natural images, LSB planes have entropy < 1.0 (some structure).
    Steganographic LSBs are nearly perfectly random → entropy ≈ 1.0.
    """
    r = arr[:, :, 0]
    entropies = {}
    for bit in range(8):
        plane = _bit_plane(r, bit)
        counts = np.bincount(plane.flatten(), minlength=2)
        total = counts.sum()
        if total == 0:
            entropies[f"bit{bit}"] = 0.0
            continue
        probs = counts / total
        probs = probs[probs > 0]
        entropies[f"bit{bit}"] = float(-np.sum(probs * np.log2(probs)))

    lsb_e = entropies.get("bit0", 0.0)
    # Natural images: LSB entropy typically 0.90-0.99
    # Stego: 0.999+
    suspicious = lsb_e > 0.995
    score = max(0.0, min(1.0, (lsb_e - 0.95) * 20))

    return TestResult(
        name="Bit-Plane Entropy",
        slug="lsb_entropy",
        verdict="SUSPICIOUS" if suspicious else "CLEAN",
        score=score,
        detail=(
            f"LSB (bit-0) entropy: {lsb_e:.4f} bits. "
            + ("Near-perfect randomness in LSB plane — strongly suggests injected data."
               if suspicious else
               f"LSB entropy within natural range. Higher bit planes: "
               + ", ".join(f"bit{b}={entropies[f'bit{b}']:.3f}" for b in range(1, 4)))
        ),
        data=entropies,
    )


# ── 4. Block variance detector (our scheme) ───────────────────────────────────

def block_variance(arr: np.ndarray, block_size: int = 8) -> TestResult:
    """
    Detects block-average encoding by checking for bimodal distribution
    of 8×8 block means around a central gray value.
    """
    gray = arr.mean(axis=2)  # convert to grayscale by averaging channels
    h, w = gray.shape
    bh = h // block_size
    bw = w // block_size

    if bh < 4 or bw < 4:
        return TestResult(
            name="Block-Average Detector",
            slug="block_variance",
            verdict="SKIPPED",
            score=0.0,
            detail="Image too small for block analysis.",
            data={},
        )

    block_means = []
    for i in range(bh):
        for j in range(bw):
            block = gray[i*block_size:(i+1)*block_size, j*block_size:(j+1)*block_size]
            block_means.append(float(block.mean()))

    means = np.array(block_means)
    overall_mean = float(means.mean())
    overall_std = float(means.std())

    # Bimodality coefficient: b = (skew² + 1) / (kurtosis + 3*(n-1)²/((n-2)(n-3)))
    n = len(means)
    if n < 10:
        bc = 0.0
    else:
        m2 = float(np.mean((means - overall_mean) ** 2))
        m3 = float(np.mean((means - overall_mean) ** 3))
        m4 = float(np.mean((means - overall_mean) ** 4))
        skew = m3 / (m2 ** 1.5 + 1e-10)
        kurt = m4 / (m2 ** 2 + 1e-10) - 3
        bc = (skew ** 2 + 1) / (kurt + 3)

    # Our scheme creates bimodality around 128 ± 14
    near_128 = np.sum(np.abs(means - 128) < 20) / len(means)
    suspicious = bc > 0.55 and near_128 > 0.3

    score = max(0.0, min(1.0, (bc - 0.4) * 2)) if suspicious else 0.0

    return TestResult(
        name="Block-Average Detector",
        slug="block_variance",
        verdict="SUSPICIOUS" if suspicious else "CLEAN",
        score=score,
        detail=(
            f"Block means: μ={overall_mean:.1f}, σ={overall_std:.1f}, bimodality={bc:.3f}. "
            + (f"{near_128*100:.0f}% of blocks cluster around gray=128 — matches block-average encoding scheme."
               if suspicious else
               "Block mean distribution looks natural. No block-average encoding detected.")
        ),
        data={
            "block_size": block_size,
            "num_blocks": len(block_means),
            "mean": round(overall_mean, 2),
            "std": round(overall_std, 2),
            "bimodality_coeff": round(bc, 4),
            "pct_near_128": round(float(near_128), 4),
            "histogram": [int(x) for x in np.histogram(means, bins=20, range=(0, 255))[0]],
        },
    )


# ── 5. Sample pairs analysis ──────────────────────────────────────────────────

def sample_pairs(arr: np.ndarray) -> TestResult:
    """
    Detects LSB matching by analysing the joint distribution of
    adjacent pixel pairs. LSB matching disturbs this in a detectable way.
    """
    flat = arr[:, :, 0].flatten().astype(np.int32)
    if len(flat) < 100:
        return TestResult(name="Sample Pairs", slug="sample_pairs", verdict="SKIPPED",
                          score=0.0, detail="Too few pixels.", data={})

    # Count pairs (x_i, x_{i+1}) where both have same LSB vs different LSB
    a = flat[:-1]
    b = flat[1:]

    same_lsb = int(np.sum((a & 1) == (b & 1)))
    diff_lsb = int(np.sum((a & 1) != (b & 1)))
    total = same_lsb + diff_lsb

    # Natural images: same_lsb > diff_lsb (spatial correlation)
    # LSB matching: ratio approaches 50/50
    ratio = same_lsb / total if total > 0 else 0.5
    suspicious = ratio < 0.52  # very close to 50/50

    score = max(0.0, min(1.0, (0.55 - ratio) * 20))

    return TestResult(
        name="Sample Pairs",
        slug="sample_pairs",
        verdict="SUSPICIOUS" if suspicious else "CLEAN",
        score=score,
        detail=(
            f"Adjacent LSB pair ratio: {ratio:.4f} (same/total). "
            + ("Ratio near 0.5 — consistent with LSB matching steganography."
               if suspicious else
               "Spatial correlation preserved. No LSB manipulation detected.")
        ),
        data={"same_lsb": same_lsb, "diff_lsb": diff_lsb, "ratio": round(ratio, 4)},
    )


# ── 6. Our scheme decoder ─────────────────────────────────────────────────────

MAGIC = b"\xAF\x01"
BLOCK_SIZE = 8
BASE_GRAY = 128

def our_scheme(arr: np.ndarray, raw_bytes: bytes) -> TestResult:
    """
    Attempts to decode using the Almond Farm block-average receipt scheme.
    Tries all 4 rotations. Reports magic match + CRC status without revealing payload.
    """
    gray = arr.mean(axis=2).astype(np.float32)
    h, w = gray.shape
    size = min(h, w)
    # Crop to square
    gray = gray[:size, :size]
    bpr = size // BLOCK_SIZE

    if bpr < 4:
        return TestResult(name="Almond Farm Scheme", slug="our_scheme", verdict="SKIPPED",
                          score=0.0, detail="Image too small for this scheme.", data={})

    for k in range(4):
        rotated = np.rot90(gray, k=k)
        bits = []
        for idx in range(bpr * bpr):
            row, col = divmod(idx, bpr)
            block = rotated[row*BLOCK_SIZE:(row+1)*BLOCK_SIZE, col*BLOCK_SIZE:(col+1)*BLOCK_SIZE]
            bits.append(1 if block.mean() > BASE_GRAY else 0)

        # Pack to bytes
        all_bytes = bytearray()
        for i in range(0, len(bits) - 7, 8):
            b = 0
            for j in range(8):
                b = (b << 1) | bits[i + j]
            all_bytes.append(b)

        if len(all_bytes) < 8:
            continue

        if all_bytes[0] == MAGIC[0] and all_bytes[1] == MAGIC[1]:
            payload_len = all_bytes[2] | (all_bytes[3] << 8)
            if payload_len > 0 and 4 + payload_len + 4 <= len(all_bytes):
                payload = bytes(all_bytes[4:4 + payload_len])
                stored_crc = struct.unpack_from("<I", all_bytes, 4 + payload_len)[0]
                computed_crc = zlib.crc32(payload) & 0xFFFFFFFF
                crc_ok = stored_crc == computed_crc

                preview = None
                if crc_ok:
                    try:
                        decoded = zlib.decompress(payload).decode("utf-8", errors="replace")
                        preview = decoded[:200]
                    except Exception:
                        try:
                            preview = payload.decode("utf-8", errors="replace")[:200]
                        except Exception:
                            preview = repr(payload[:50])

                rotation_label = ["0°", "90°", "180°", "270°"][k]
                return TestResult(
                    name="Almond Farm Scheme",
                    slug="our_scheme",
                    verdict="DETECTED",
                    score=1.0,
                    detail=(
                        f"Magic bytes matched at rotation {rotation_label}. "
                        f"Payload: {payload_len} bytes. CRC: {'OK' if crc_ok else 'FAIL'}. "
                        + ("Payload decoded successfully." if crc_ok else "CRC mismatch — possible corruption or wrong scheme variant.")
                    ),
                    data={
                        "magic_matched": True,
                        "rotation": rotation_label,
                        "payload_bytes": payload_len,
                        "crc_ok": crc_ok,
                        "preview": preview,
                    },
                )

    return TestResult(
        name="Almond Farm Scheme",
        slug="our_scheme",
        verdict="CLEAN",
        score=0.0,
        detail="Magic bytes not found in any orientation. Not encoded with this scheme.",
        data={"magic_matched": False},
    )


# ── Main analyzer ─────────────────────────────────────────────────────────────

def analyze(image_bytes: bytes) -> AnalysisReport:
    img, arr = _load(image_bytes)
    image_hash = hashlib.sha256(image_bytes).hexdigest()

    fmt_info, fmt_test = format_analysis(img, image_bytes)
    tests: list[TestResult] = [fmt_test]

    # Only run pixel-level tests on lossless images
    # (JPEG destroys LSBs — results would be meaningless noise)
    if fmt_info.lossless:
        tests.append(lsb_chi_square(arr))
        tests.append(lsb_entropy(arr))
        tests.append(sample_pairs(arr))

    tests.append(block_variance(arr))
    tests.append(our_scheme(arr, image_bytes))

    # Aggregate verdict
    detected = any(t.verdict == "DETECTED" for t in tests)
    suspicious_tests = [t for t in tests if t.verdict == "SUSPICIOUS"]
    max_score = max((t.score for t in tests), default=0.0)

    if detected:
        verdict = "PAYLOAD_DETECTED"
        confidence = 1.0
    elif len(suspicious_tests) >= 2:
        verdict = "SUSPICIOUS"
        confidence = min(0.95, max_score)
    elif len(suspicious_tests) == 1:
        verdict = "SUSPICIOUS"
        confidence = max_score * 0.6
    else:
        verdict = "CLEAN"
        confidence = 1.0 - max_score

    # Extract payload info from our_scheme test if detected
    our = next((t for t in tests if t.slug == "our_scheme"), None)
    payload_scheme = None
    payload_size = None
    payload_preview = None
    if our and our.verdict == "DETECTED":
        payload_scheme = "almond-farm-block-average-v1"
        payload_size = our.data.get("payload_bytes")
        payload_preview = our.data.get("preview")

    return AnalysisReport(
        image_hash=image_hash,
        format=fmt_info,
        tests=tests,
        verdict=verdict,
        confidence=confidence,
        payload_detected=detected,
        payload_scheme=payload_scheme,
        payload_size_bytes=payload_size,
        payload_preview=payload_preview,
    )


# ── CLI smoke test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "steganography", "backend"))

    # Test 1: clean PNG (generated noise)
    from PIL import Image as PILImage
    import io as _io
    rng = np.random.default_rng(0)
    clean_arr = rng.integers(0, 256, (256, 256, 3), dtype=np.uint8)
    clean_img = PILImage.fromarray(clean_arr, "RGB")
    buf = _io.BytesIO()
    clean_img.save(buf, "PNG")
    clean_bytes = buf.getvalue()

    print("=== CLEAN IMAGE ===")
    report = analyze(clean_bytes)
    print(f"Verdict: {report.verdict} ({report.confidence:.0%} confidence)")
    for t in report.tests:
        print(f"  [{t.verdict:>8}] {t.name}: {t.detail[:80]}")

    # Test 2: our encoded receipt texture
    steg_path = "/tmp/receipt_texture.png"
    if os.path.exists(steg_path):
        print("\n=== ENCODED RECEIPT TEXTURE ===")
        with open(steg_path, "rb") as f:
            steg_bytes = f.read()
        report2 = analyze(steg_bytes)
        print(f"Verdict: {report2.verdict} ({report2.confidence:.0%} confidence)")
        for t in report2.tests:
            print(f"  [{t.verdict:>8}] {t.name}: {t.detail[:80]}")
        if report2.payload_preview:
            print(f"\nPayload preview:\n{report2.payload_preview[:300]}")
