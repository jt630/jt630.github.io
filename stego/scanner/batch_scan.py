#!/usr/bin/env python3
"""
batch_scan.py — Download images and run stego analysis on each one.

Usage:
    python batch_scan.py --urls nft_images.txt --out results.json

    # Scan a local directory:
    python batch_scan.py --dir ./downloaded_images/ --out results.json

    # Show only suspicious results:
    python batch_scan.py --urls nft_images.txt --out results.json --suspicious-only

    # Resume interrupted scan:
    python batch_scan.py --urls nft_images.txt --out results.json  # auto-resumes

Requirements:
    pip install requests pillow numpy

Output:
    JSON file with one entry per image, sorted by suspicion score descending.
    Prints a live leaderboard of top suspicious images as it runs.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import struct
import sys
import time
from pathlib import Path
from typing import Optional

import requests
import numpy as np
from PIL import Image

# ── Inline stego analyzer (subset — LSB chi², entropy, STEG decode) ──────────
# Full analyzer requires jpegio for DCT test. We run what we can without it.

STEG_MAGIC = b"STEG"


def _entropy(values: np.ndarray) -> float:
    counts = np.bincount(values.flatten().astype(np.uint8), minlength=256)
    probs = counts[counts > 0] / counts.sum()
    return float(-np.sum(probs * np.log2(probs)))


def _chi2_p(chi2: float, df: int) -> float:
    """Approximate chi-square p-value."""
    if chi2 <= 0:
        return 1.0
    k = df / 2.0
    x = chi2 / 2.0
    # Regularized incomplete gamma (series approximation)
    try:
        import math
        if x == 0:
            return 1.0
        log_gamma_k = math.lgamma(k)
        # Use scipy if available for accuracy
        try:
            from scipy.stats import chi2 as chi2_dist
            return float(1 - chi2_dist.cdf(chi2, df))
        except ImportError:
            pass
        # Fallback: rough approximation
        z = (chi2 - df) / math.sqrt(2 * df)
        return float(0.5 * (1 - math.erf(z / math.sqrt(2))))
    except Exception:
        return 0.5


def analyze_image(img_bytes: bytes) -> dict:
    """Run stego tests on image bytes. Returns a result dict."""
    result = {
        "size_bytes": len(img_bytes),
        "format": None,
        "dimensions": None,
        "lsb_score": 0.0,
        "lsb_chi2": None,
        "lsb_p": None,
        "lsb0_entropy": None,
        "steg_found": False,
        "steg_message": None,
        "suspicion_score": 0.0,
        "flags": [],
    }

    try:
        img = Image.open(io.BytesIO(img_bytes))
        result["format"] = img.format
        result["dimensions"] = f"{img.width}x{img.height}"
        arr = np.array(img.convert("RGB"), dtype=np.uint8)
    except Exception as e:
        result["flags"].append(f"load_error: {e}")
        return result

    flat = arr.flatten()

    # ── LSB chi-square ────────────────────────────────────────────────────────
    lsbs = flat & 1
    pairs = flat[:-1:2].astype(np.int32)
    # Count (2k, 2k+1) value pairs
    n_even = np.sum((flat[:-1:2] & 1) == 0)
    n_odd  = np.sum((flat[:-1:2] & 1) == 1)
    total  = n_even + n_odd
    if total > 0:
        expected = total / 2
        chi2 = ((n_even - expected) ** 2 + (n_odd - expected) ** 2) / expected
        p = _chi2_p(chi2, 1)
        result["lsb_chi2"] = round(float(chi2), 4)
        result["lsb_p"] = round(float(p), 6)
        # High p = pairs too equal = suspicious for stego
        if p > 0.9:
            result["flags"].append(f"lsb_chi2_suspicious (p={p:.3f})")
            result["lsb_score"] = float(p)

    # ── LSB bit-plane entropy ─────────────────────────────────────────────────
    lsb_plane = (arr[:, :, 0] & 1).flatten()
    entropy = _entropy(np.array([lsb_plane.sum(), len(lsb_plane) - lsb_plane.sum()]))
    result["lsb0_entropy"] = round(float(entropy), 4)
    if entropy > 0.99:
        result["flags"].append(f"lsb_entropy_high ({entropy:.4f})")

    # ── STEG magic decode ─────────────────────────────────────────────────────
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
    if magic == STEG_MAGIC:
        length_bytes = read_bytes(32, 4)
        length = struct.unpack(">I", length_bytes)[0]
        max_payload = (len(flat) - 64) // 8
        if 0 < length <= max_payload:
            payload = read_bytes(64, length)
            try:
                message = payload.decode("utf-8")
                result["steg_found"] = True
                result["steg_message"] = message[:500]
                result["flags"].append("STEG_MAGIC_FOUND")
            except UnicodeDecodeError:
                result["steg_found"] = True
                result["steg_message"] = "[binary payload]"
                result["flags"].append("STEG_MAGIC_FOUND_BINARY")

    # ── Composite suspicion score ─────────────────────────────────────────────
    score = 0.0
    if result["steg_found"]:
        score = 1.0
    elif result["lsb_score"] > 0.95:
        score = result["lsb_score"]
    elif result["lsb_score"] > 0.9:
        score = result["lsb_score"] * 0.8
    result["suspicion_score"] = round(score, 4)

    return result


# ── Downloader ────────────────────────────────────────────────────────────────

IPFS_GATEWAYS = [
    "https://ipfs.io/ipfs/",
    "https://cloudflare-ipfs.com/ipfs/",
    "https://gateway.pinata.cloud/ipfs/",
]


def download_image(url: str, timeout: int = 20) -> Optional[bytes]:
    """Download an image, trying IPFS fallbacks if needed."""
    urls_to_try = [url]

    # If IPFS URL, also try alternate gateways
    if "/ipfs/" in url:
        cid_path = url.split("/ipfs/", 1)[1]
        for gw in IPFS_GATEWAYS:
            alt = gw + cid_path
            if alt != url:
                urls_to_try.append(alt)

    for attempt_url in urls_to_try:
        try:
            r = requests.get(attempt_url, timeout=timeout, stream=True)
            r.raise_for_status()
            # Limit to 50MB
            chunks = []
            total = 0
            for chunk in r.iter_content(65536):
                chunks.append(chunk)
                total += len(chunk)
                if total > 50 * 1024 * 1024:
                    break
            return b"".join(chunks)
        except Exception:
            continue
    return None


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Batch stego scanner for NFT images")
    parser.add_argument("--urls", help="Text file with one image URL per line")
    parser.add_argument("--dir", help="Directory of local image files")
    parser.add_argument("--out", default="scan_results.json", help="Output JSON file")
    parser.add_argument("--suspicious-only", action="store_true", help="Only save suspicious results")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between downloads (seconds)")
    parser.add_argument("--workers", type=int, default=1, help="Parallel workers (experimental)")
    args = parser.parse_args()

    if not args.urls and not args.dir:
        parser.print_help()
        sys.exit(1)

    # Build work list
    if args.urls:
        items = Path(args.urls).read_text().splitlines()
        items = [u.strip() for u in items if u.strip()]
        source = "url"
    else:
        items = list(Path(args.dir).glob("*"))
        items = [str(p) for p in items if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}]
        source = "file"

    out_path = Path(args.out)

    # Load existing results for resume
    done = {}
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text())
            done = {r["url"]: r for r in existing}
            print(f"Resuming — {len(done)} already scanned")
        except Exception:
            pass

    print(f"\nScanning {len(items)} images")
    print(f"Output: {out_path}\n")

    results = list(done.values())
    suspicious = [r for r in results if r.get("suspicion_score", 0) > 0.5]

    for i, item in enumerate(items):
        if item in done:
            continue

        # Progress
        if i % 50 == 0:
            print(f"  [{i}/{len(items)}]  suspicious so far: {len(suspicious)}")

        # Download or read
        if source == "url":
            img_bytes = download_image(item)
        else:
            try:
                img_bytes = Path(item).read_bytes()
            except Exception:
                img_bytes = None

        if not img_bytes:
            result = {"url": item, "error": "download_failed", "suspicion_score": 0.0}
        else:
            result = analyze_image(img_bytes)
            result["url"] = item

        if not args.suspicious_only or result.get("suspicion_score", 0) > 0.1:
            results.append(result)

        if result.get("suspicion_score", 0) > 0.5:
            suspicious.append(result)
            print(f"\n  *** SUSPICIOUS: {item}")
            print(f"      Score: {result['suspicion_score']}")
            print(f"      Flags: {result['flags']}")
            if result.get("steg_message"):
                print(f"      Message: {result['steg_message'][:100]}")
            print()

        if result.get("steg_found"):
            print(f"\n  !!! STEG MESSAGE FOUND: {item}")
            print(f"      {result.get('steg_message', '')[:200]}\n")

        # Save progress every 100
        if i % 100 == 0:
            results_sorted = sorted(results, key=lambda x: x.get("suspicion_score", 0), reverse=True)
            out_path.write_text(json.dumps(results_sorted, indent=2))

        time.sleep(args.delay)

    # Final save — sorted by suspicion score
    results_sorted = sorted(results, key=lambda x: x.get("suspicion_score", 0), reverse=True)
    out_path.write_text(json.dumps(results_sorted, indent=2))

    print(f"\n{'='*60}")
    print(f"Scan complete. {len(results)} images analyzed.")
    print(f"Suspicious (score > 0.5): {len(suspicious)}")
    print(f"STEG messages found: {sum(1 for r in results if r.get('steg_found'))}")
    print(f"\nFull results: {out_path}")

    # Print top 10
    if suspicious:
        print(f"\nTop suspicious images:")
        for r in results_sorted[:10]:
            if r.get("suspicion_score", 0) > 0:
                print(f"  {r['suspicion_score']:.3f}  {r['url'][:80]}")
                if r.get("flags"):
                    print(f"         {r['flags']}")


if __name__ == "__main__":
    main()
