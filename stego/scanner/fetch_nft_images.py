#!/usr/bin/env python3
"""
fetch_nft_images.py — Pull image URLs from any ERC-721 NFT collection on Polygon/Ethereum.

Usage:
    python fetch_nft_images.py --contract 0x24a11e702cd90f034ea44faf1e180c0c654ac5d9 \
                               --supply 45000 \
                               --out trump_s1_images.txt \
                               --rpc https://polygon-rpc.com

    # Or resume from a token ID:
    python fetch_nft_images.py --contract 0x... --supply 45000 --start 1000

Requirements:
    pip install requests

Output:
    A text file with one image URL per line, ready to feed into batch_scan.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

# ── Polygon RPC options (try in order) ───────────────────────────────────────
DEFAULT_RPCS = [
    "https://polygon-rpc.com",
    "https://rpc.ankr.com/polygon",
    "https://rpc-mainnet.matic.network",
    "https://matic-mainnet.chainstacklabs.com",
]

# ── IPFS gateways (try in order) ─────────────────────────────────────────────
IPFS_GATEWAYS = [
    "https://ipfs.io/ipfs/",
    "https://cloudflare-ipfs.com/ipfs/",
    "https://gateway.pinata.cloud/ipfs/",
    "https://dweb.link/ipfs/",
]

# tokenURI(uint256) selector
TOKEN_URI_SELECTOR = "0xc87b56dd"


def rpc_call(rpc_url: str, contract: str, token_id: int, timeout: int = 10) -> str | None:
    """Call tokenURI(token_id) on contract, return the URI string or None."""
    padded = hex(token_id)[2:].zfill(64)
    data = TOKEN_URI_SELECTOR + padded

    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": contract, "data": data}, "latest"],
        "id": token_id,
    }

    try:
        r = requests.post(rpc_url, json=payload, timeout=timeout)
        r.raise_for_status()
        result = r.json().get("result", "")
        if not result or result == "0x":
            return None
        return decode_abi_string(bytes.fromhex(result[2:]))
    except Exception:
        return None


def decode_abi_string(data: bytes) -> str:
    """Decode ABI-encoded string returned by eth_call."""
    try:
        offset = int.from_bytes(data[0:32], "big")
        length = int.from_bytes(data[offset : offset + 32], "big")
        return data[offset + 32 : offset + 32 + length].decode("utf-8")
    except Exception:
        return ""


def ipfs_to_http(uri: str) -> str:
    """Convert ipfs:// URI to HTTP gateway URL."""
    if uri.startswith("ipfs://"):
        cid = uri[7:]
        return IPFS_GATEWAYS[0] + cid
    return uri


def fetch_metadata(uri: str, timeout: int = 15) -> dict | None:
    """Fetch JSON metadata from a token URI (IPFS or HTTP)."""
    url = ipfs_to_http(uri)
    for gateway in IPFS_GATEWAYS:
        try:
            # Swap gateway if needed
            if "ipfs.io" in url:
                attempt_url = url
            else:
                cid_path = url.split("/ipfs/", 1)[-1] if "/ipfs/" in url else url
                attempt_url = gateway + cid_path

            r = requests.get(attempt_url, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception:
            continue
    return None


def find_working_rpc(rpcs: list[str], contract: str) -> str | None:
    """Test RPCs and return the first working one."""
    print("Finding working RPC endpoint...")
    for rpc in rpcs:
        result = rpc_call(rpc, contract, 1, timeout=8)
        if result:
            print(f"  ✓ {rpc}")
            return rpc
        print(f"  ✗ {rpc}")
    return None


def main():
    parser = argparse.ArgumentParser(description="Fetch NFT image URLs from an ERC-721 contract")
    parser.add_argument("--contract", required=True, help="Contract address")
    parser.add_argument("--supply", type=int, required=True, help="Total token supply")
    parser.add_argument("--start", type=int, default=1, help="Start token ID (default: 1)")
    parser.add_argument("--out", default="nft_images.txt", help="Output file for image URLs")
    parser.add_argument("--rpc", help="Polygon RPC URL (auto-detected if not set)")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between RPC calls (seconds)")
    parser.add_argument("--batch", type=int, default=100, help="Save progress every N tokens")
    args = parser.parse_args()

    contract = args.contract.lower()
    if not contract.startswith("0x"):
        contract = "0x" + contract

    rpc = args.rpc or find_working_rpc(DEFAULT_RPCS, contract)
    if not rpc:
        sys.exit("No working RPC found. Try providing one with --rpc")

    out_path = Path(args.out)
    existing = set()
    if out_path.exists():
        existing = set(out_path.read_text().splitlines())
        print(f"Resuming — {len(existing)} URLs already collected")

    print(f"\nScanning {args.supply - args.start + 1} tokens on {rpc}")
    print(f"Contract: {contract}")
    print(f"Output:   {out_path}\n")

    collected = 0
    errors = 0

    with out_path.open("a") as f:
        for token_id in range(args.start, args.supply + 1):
            # Progress
            if token_id % args.batch == 0:
                print(f"  Token {token_id}/{args.supply}  collected={collected}  errors={errors}")

            # Get token URI
            uri = rpc_call(rpc, contract, token_id)
            if not uri:
                errors += 1
                time.sleep(args.delay)
                continue

            # Fetch metadata JSON
            metadata = fetch_metadata(uri)
            if not metadata:
                errors += 1
                time.sleep(args.delay)
                continue

            # Extract image URL
            image_url = metadata.get("image", "")
            if not image_url:
                errors += 1
                continue

            # Convert IPFS to HTTP
            image_http = ipfs_to_http(image_url)

            if image_http not in existing:
                f.write(image_http + "\n")
                f.flush()
                existing.add(image_http)
                collected += 1

            time.sleep(args.delay)

    print(f"\nDone. {collected} image URLs saved to {out_path}")
    print(f"Errors: {errors}")
    print(f"\nNext step:")
    print(f"  python batch_scan.py --urls {out_path} --out scan_results.json")


if __name__ == "__main__":
    main()
