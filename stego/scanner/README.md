# NFT Stego Scanner

Scans NFT collections for hidden steganographic content.

## Install

```bash
pip install requests pillow numpy
```

## Scan Trump Digital Trading Cards (Series 1 — 45,000 cards)

```bash
# Step 1: Pull all image URLs from the blockchain (~2 hours, saves progress)
python fetch_nft_images.py \
  --contract 0x24a11e702cd90f034ea44faf1e180c0c654ac5d9 \
  --supply 45000 \
  --out trump_s1_images.txt

# Step 2: Scan them all for stego content (~4-8 hours, auto-resumes)
python batch_scan.py \
  --urls trump_s1_images.txt \
  --out trump_s1_results.json \
  --suspicious-only
```

## Scan any other collection

```bash
python fetch_nft_images.py --contract <address> --supply <count> --out images.txt
python batch_scan.py --urls images.txt --out results.json
```

## Scan local images

```bash
python batch_scan.py --dir ./my_images/ --out results.json
```

## What it detects

- **STEG magic header** — our own LSB encoding scheme (definitive find)
- **LSB chi-square anomaly** — statistical signature of LSB replacement
- **High LSB entropy** — randomized LSB plane = likely encoded data

## Output

`results.json` sorted by suspicion score. Top of the file = most suspicious.

Each entry:
```json
{
  "url": "https://ipfs.io/ipfs/Qm...",
  "suspicion_score": 0.97,
  "steg_found": true,
  "steg_message": "...",
  "flags": ["STEG_MAGIC_FOUND"],
  "lsb_chi2": 0.12,
  "lsb_p": 0.97,
  "format": "PNG",
  "dimensions": "1024x1024"
}
```
