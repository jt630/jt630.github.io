#!/usr/bin/env python3
"""
generate_monkey_post.py — Infinite Monkey Theorem post generator

Workflow:
  1. Read monkey registry → find entry by key
  2. Call Claude API → generate transcript (500–2000 words in target language)
  3. Derive token_id = keccak256(monkey_key | date | transcript)
  4. Derive ML-DSA-65 PQ keypair seeded from SHA-3(transcript)
     → transcript IS the private key; whoever holds it can rederive sk
  5. Write post .md with full front matter (pq_pubkey embedded)
  6. Print PQ secret key to stdout — never stored on site or on-chain
  7. Update registry entry (owner, owner_date, token_id, pq_pubkey)

Usage:
  python scripts/generate_monkey_post.py --key Liam_US_2023 --owner gh:username

Dependencies (pip install):
  anthropic
  pyyaml
  dilithium-py          # pure-Python ML-DSA (FIPS 204) — seed-based keygen
  pycryptodome          # keccak256 (EVM-compatible)

Security design:
  Content layer  → keccak256(key+date+transcript)  → quantum-resistant (Grover: 256→128 bit)
  Ownership layer → ML-DSA-65 pubkey in metadata    → quantum-resistant (FIPS 204)
  ETH wallet     → ECDSA secp256k1                  → quantum-vulnerable (Shor's); ETH will migrate
"""

import argparse
import hashlib
import sys
from datetime import date
from pathlib import Path

import anthropic
import yaml

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "data" / "monkey_registry.yaml"
CONTENT_DIR = ROOT / "content" / "monkeys"

# ---------------------------------------------------------------------------
# Cryptographic primitives
# ---------------------------------------------------------------------------

def keccak256_hex(data: bytes) -> str:
    """EVM-compatible keccak-256. Returns '0x…' hex string."""
    from Crypto.Hash import keccak
    k = keccak.new(digest_bits=256)
    k.update(data)
    return "0x" + k.hexdigest()


def derive_token_id(monkey_key: str, post_date: str, transcript: str) -> str:
    """
    Content commitment: keccak256(monkey_key | YYYYMMDD | transcript).
    Quantum-resistant: Grover's gives √ speedup → 128-bit post-quantum security.
    Tampering with the transcript changes the hash → token ID no longer matches.
    """
    raw = f"{monkey_key}|{post_date}|{transcript}".encode("utf-8")
    return keccak256_hex(raw)


def derive_pq_keypair(transcript: str) -> tuple[bytes, bytes]:
    """
    Derive a deterministic ML-DSA-65 (Dilithium3 / FIPS 204) keypair from the transcript.

    The transcript IS the private key:
        seed = SHA-3-256(transcript)   [32 bytes]
        (pk, sk) = ML-DSA-65.KeyGen(seed)

    Whoever holds the transcript can rederive sk. The pubkey goes on-chain;
    the secret key is given to the owner and never stored.

    Requires: pip install dilithium-py
    """
    try:
        from dilithium_py.dilithium import Dilithium3
    except ImportError:
        print(
            "ERROR: dilithium-py not installed. Run: pip install dilithium-py",
            file=sys.stderr,
        )
        sys.exit(1)

    seed = hashlib.sha3_256(transcript.encode("utf-8")).digest()  # 32 bytes
    pk, sk = Dilithium3.keygen_from_seed(seed)
    return pk, sk


# ---------------------------------------------------------------------------
# Transcript generation
# ---------------------------------------------------------------------------

TRANSMISSION_PROMPT = """You are {name}, a monkey named after the #1 baby name of \
{source_year} in {country}. You type in {language}. You are participating in the \
Infinite Monkey Theorem experiment — typing continuously until, collectively, all \
monkeys have produced Hamlet in every language.

Write one transmission: a stream-of-consciousness prose passage.

Rules:
- 500–2000 words
- Written entirely in {language} — no translation, no English, no code-switching
- Raw, unedited typing — you are a monkey at a typewriter; thoughts cascade
- Let fragments of Shakespeare's imagery surface naturally and unexpectedly
- No title, no headers, no meta-commentary — just the text

Begin."""


def generate_transcript(monkey: dict) -> str:
    """Call Claude API to generate a monkey transmission."""
    client = anthropic.Anthropic()

    system = TRANSMISSION_PROMPT.format(
        name=monkey["name"],
        source_year=monkey["source_year"],
        country=monkey["country_code"],
        language=monkey["language_code"],
    )

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": "Type your transmission."}],
    )
    return message.content[0].text.strip()


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def load_registry() -> dict:
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"monkeys": []}


def save_registry(registry: dict) -> None:
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        yaml.dump(registry, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def find_monkey(registry: dict, key: str) -> dict | None:
    return next((m for m in (registry.get("monkeys") or []) if m.get("key") == key), None)


# ---------------------------------------------------------------------------
# Transmission counter — find next "transmission N" for this monkey
# ---------------------------------------------------------------------------

def next_transmission_number(monkey_key: str) -> int:
    slug = monkey_key.lower().replace("_", "-")
    existing = list(CONTENT_DIR.glob(f"{slug}_*.md"))
    return len(existing) + 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an Infinite Monkey Theorem post.")
    parser.add_argument("--key", required=True, help="Monkey key, e.g. Liam_US_2023")
    parser.add_argument("--owner", default="anon", help="Owner identifier, e.g. gh:username")
    parser.add_argument("--dry-run", action="store_true", help="Generate transcript but do not write files")
    args = parser.parse_args()

    # Load registry
    registry = load_registry()
    monkey = find_monkey(registry, args.key)
    if monkey is None:
        print(f"ERROR: monkey '{args.key}' not found in registry.", file=sys.stderr)
        sys.exit(1)

    today = date.today()
    today_yyyymmdd = today.strftime("%Y%m%d")
    today_iso = today.isoformat()

    # Check for duplicate (same monkey + same date)
    slug = args.key.lower().replace("_", "-")
    target_file = CONTENT_DIR / f"{slug}_{today_yyyymmdd}.md"
    if target_file.exists() and not args.dry_run:
        print(f"ERROR: {target_file} already exists. A coin can only be pressed once per day.", file=sys.stderr)
        sys.exit(1)

    print(f"Generating transmission for {args.key} on {today_iso}…")
    transcript = generate_transcript(monkey)

    word_count = len(transcript.split())
    if word_count < 500:
        print(f"WARNING: transcript is only {word_count} words (minimum 500). Proceeding anyway.")

    print(f"Transcript: {word_count} words")

    # --- Content commitment (quantum-resistant) ---
    token_id = derive_token_id(args.key, today_yyyymmdd, transcript)
    print(f"Token ID:   {token_id}")

    # --- PQ keypair derivation ---
    print("Deriving ML-DSA-65 keypair from transcript…")
    pq_pk, pq_sk = derive_pq_keypair(transcript)
    pq_pk_hex = pq_pk.hex()
    pq_sk_hex = pq_sk.hex()
    print(f"PQ pubkey:  {pq_pk_hex[:32]}…")

    if args.dry_run:
        print("\n[dry-run] No files written.")
        print(f"Transcript preview:\n{transcript[:300]}…")
        return

    # --- Build front matter ---
    n = next_transmission_number(args.key)
    title = f"transmission {n}"

    description = " ".join(transcript.split()[:20]) + "…"

    front_matter = {
        "title": title,
        "date": today_iso,
        "monkey_key": args.key,
        "monkey": monkey["name"],
        "country": monkey["country_code"],
        "language": monkey["language_code"],
        "source_year": monkey["source_year"],
        "description": description,
        "owner": args.owner,
        "owner_date": today_iso,
        "token_id": token_id,
        "pq_pubkey": pq_pk_hex,
        "pq_scheme": "ML-DSA-65",
        "milestones": [],
    }

    post_content = "---\n" + yaml.dump(front_matter, allow_unicode=True, sort_keys=False) + "---\n\n" + transcript + "\n"

    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    target_file.write_text(post_content, encoding="utf-8")
    print(f"Post written: {target_file.relative_to(ROOT)}")

    # --- Update registry ---
    monkey["post_date"] = today_iso
    monkey["file"] = str(target_file.relative_to(ROOT))
    monkey.setdefault("owner", args.owner)
    monkey.setdefault("owner_date", today_iso)
    save_registry(registry)
    print(f"Registry updated: {REGISTRY_PATH.relative_to(ROOT)}")

    # --- Print PQ secret key to stdout ---
    print()
    print("=" * 70)
    print("  OWNER SECRET — ML-DSA-65 POST-QUANTUM PRIVATE KEY")
    print("  Save this. Do not share it. It is not stored anywhere.")
    print("=" * 70)
    print(pq_sk_hex)
    print("=" * 70)
    print()
    print("This key proves post-quantum ownership of your coin.")
    print("It is derived from the transcript. Lose the transcript, lose the key.")
    print(f"Verify:  SHA-3-256(transcript) → first 32 bytes → ML-DSA-65 seed")
    print(f"Pubkey on-chain: {pq_pk_hex[:64]}…")


if __name__ == "__main__":
    main()
