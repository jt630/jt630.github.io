# NFT Stego Scanner

Scans NFT collections for hidden steganographic content using LSB chi-square,
entropy analysis, and STEG magic header detection.

---

## Context (read this first)

Built during the Stego session (branch `claude/stego-analyzer-NZoTZ`). The goal
is to scan the Trump Digital Trading Cards NFT collection — 45,000 AI-generated
images on Polygon — for steganographic content. Nobody has done this publicly.

The hypothesis: NFT image pipelines and/or creators may have embedded hidden
data in pixel LSBs. The blockchain provides built-in key distribution (token
transfers as signals) making NFTs a plausible covert channel.

**Target contract:** `0x24a11e702cd90f034ea44faf1e180c0c654ac5d9` (Polygon, Series 1)

---

## Install

```bash
pip install requests pillow numpy
```

---

## Resource requirements

| Step | Time | RAM | Disk |
|------|------|-----|------|
| fetch_nft_images.py (45k tokens) | ~6–10 hrs | <50MB | ~4MB (URL list) |
| batch_scan.py (45k images) | ~12–20 hrs | <200MB peak | ~20MB (results JSON) |

- **Memory is not the bottleneck** — images are processed one at a time and discarded
- **Network is the bottleneck** — IPFS gateways are slow and sometimes flaky
- Both scripts **auto-resume** — safe to ctrl+C and restart, no work is lost
- Run overnight, check results in the morning

---

## Step 1 — Fetch image URLs from the blockchain

```bash
python fetch_nft_images.py \
  --contract 0x24a11e702cd90f034ea44faf1e180c0c654ac5d9 \
  --supply 45000 \
  --out trump_s1_images.txt
```

This calls `tokenURI(n)` for each token ID via Polygon RPC, fetches the IPFS
metadata JSON, extracts the image URL, and appends it to the output file.
Progress is saved continuously — if it fails at token 12,000, restart with
`--start 12001`.

If the default RPC is slow, try:
```bash
--rpc https://rpc.ankr.com/polygon
```

---

## Step 2 — Scan all images for stego content

```bash
python batch_scan.py \
  --urls trump_s1_images.txt \
  --out trump_s1_results.json
```

Downloads each image, runs 3 detection tests, saves results sorted by suspicion
score. Prints live alerts if anything suspicious is found.

---

## What a find looks like

**Definitive — STEG magic header:**
```
!!! STEG MESSAGE FOUND: https://ipfs.io/ipfs/QmXXXXX/4721.png
    [decoded message here]
```

**Statistical anomaly (high suspicion, unknown scheme):**
```
*** SUSPICIOUS: https://ipfs.io/ipfs/QmXXXXX/8832.png
    Score: 0.94
    Flags: ['lsb_chi2_suspicious (p=0.96)', 'lsb_entropy_high (0.9991)']
```
For these, bring the image URL back to a Claude session and run it through
the full stego backend (`stego/backend/analyzer.py`) which includes DCT
chi-square for JPEG stego detection.

---

## Other collections to scan

| Collection | Contract | Chain | Supply |
|-----------|---------|-------|--------|
| Trump Cards Series 1 | `0x24a11e702cd90f034ea44faf1e180c0c654ac5d9` | Polygon | 45,000 |
| Trump Cards Series 2 | TBD | Polygon | TBD |
| Bored Ape Yacht Club | `0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D` | Ethereum | 10,000 |

For Ethereum contracts, use `--rpc https://eth.llamarpc.com`

---

## What it detects

| Test | Signal | What it means |
|------|--------|---------------|
| STEG magic decode | `STEG` header in LSB stream | Definitive — encoded with our scheme |
| LSB chi-square | p > 0.9 | LSB pairs too balanced — not natural |
| LSB entropy | entropy > 0.99 | LSB plane maximally random — likely encoded |

---

## Output format

`results.json` — sorted by suspicion score descending (most suspicious first).

```json
{
  "url": "https://ipfs.io/ipfs/Qm...",
  "suspicion_score": 0.97,
  "steg_found": true,
  "steg_message": "...",
  "flags": ["STEG_MAGIC_FOUND"],
  "lsb_chi2": 0.12,
  "lsb_p": 0.97,
  "lsb0_entropy": 0.9994,
  "format": "PNG",
  "dimensions": "1024x1024",
  "size_bytes": 1843200
}
```
