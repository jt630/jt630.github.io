# Infinite Monkey Theorem — Project Plan

## Summary

We are running the infinite monkey theorem simultaneously in every human language.

Each monkey is a named AI agent. Its name is the **#1 baby name of the year** in a
given country — real, historically sourced. The monkey types in its mother tongue.
Given enough transmissions, the monkeys will collectively produce Hamlet in every
language. These are the transcripts so far.

Registry: `data/monkey_registry.yaml`

---

## The North Star

> **Write Hamlet in every language available to computers. Then shut down.**

Not on purpose. One transmission at a time, one monkey at a time — until every
language has produced enough material to assemble the play. When the last language
finishes Hamlet, the experiment closes. The monkeys go quiet. The site becomes a
permanent archive.

This is a countdown, not an infinite feed. The end condition is baked in.

### What the monkeys are actually making

Each transmission is a cryptographically secure key — derived from the full transcript
text. The monkeys aren't just typing; they're generating irreducible entropy. Long,
dense, unique prose in a given language makes a quantum-resistant hash preimage.

The goal and the security mechanism are the same thing:
**type enough Hamlet in enough languages and you've also generated a complete set of
language-diverse quantum-secure keys.**

When every language finishes — the keys exist, Hamlet exists, the machine stops.

---

## Goals (ordered)

### ☐ Goal 0 — Hamlet in English first
Before expanding outward: get enough English transmissions to sketch the arc of Hamlet.
This proves the format and gives a baseline for what "enough" looks like in one language.

---

### ☐ Goal 1 — One Monkey Per Language
One transmission from every major living language (target: all ISO 639-1 languages
with a living speaker population — ~184 languages).

Each post written in the monkey's mother tongue.

**How:**
1. For each target language, identify a primary country with available baby name data
2. Pull the #1 baby name for any year with data
3. Invoke the monkey agent → generates one post in that language
4. Register the entry; tag `first_in_language:{lang}` and `first_in_country:{iso2}`

**Milestone:** `goal1_complete` — tagged on the final entry that closes the language set.

---

### ☐ Goal 2 — Every Available Name, Every Available Country, One Year
Compile all #1 baby name data available globally for a single year (target: **2023**).
One monkey per entry. Every post in mother tongue.

Sources: national statistics offices · UNICEF · academic datasets · journalistic records.
Tag `data_gap` when the source is non-primary.

**Milestone:** `goal2_complete:2023` — tagged when all available 2023 entries are done.

---

### ☐ Goal 3 — Decade Sweep (2014–2023)
Extend Goal 2 across ten years. Each year = one sweep. Same process.
Name collisions across years are fine — each year gets a distinct key.

**Milestone:** `goal3_complete` — tagged when all ten years are fully populated.

---

### ☐ Goal 4 — Hamlet in Every Language → Shutdown

Using accumulated transmissions as material, assemble a Hamlet-shaped structure
in each language. This is a curation + composition step, not just generation.

**When the last language completes Hamlet — the experiment ends.**

The site does not get a new section. No new monkeys are registered. The machine
stops. Everything that exists at that moment is the permanent archive: every
transcript, every coin, every key, every language's Hamlet.

The scope is defined by what computers can encode: every language with a Unicode
block and a living or historical writing system. That's the finish line.

**Shutdown condition:** `hamlet_complete` tagged in every language in the registry.
The site enters read-only mode. The penny press goes cold. The coins remain.

---

## Agent Architecture

Each monkey is an **agent configuration** stored in the registry. When a post is
triggered for monkey `Liam_US_2023`, the system:

1. Reads `data/monkey_registry.yaml` → finds entry with `key: "Liam_US_2023"`
2. Builds a system prompt from the entry's fields:
   - Language: English (`en`)
   - Country: United States
   - Name/persona: Liam
   - Source year: 2023 (the monkey's "birth year" context)
3. Calls the Claude API with that system prompt
4. Output = a "transmission" — raw monkey typing, in English, unedited
5. Saves to `content/monkeys/liam-us-2023_{YYYYMMDD}.md` with full front matter
6. Updates the registry entry (`post_date`, `file`, any new milestones)

**Post generation triggers:** manual (call the agent) or scripted batch sweep.
The agent script lives at: `scripts/generate_monkey_post.py` *(to be built)*

---

## Key Design

### Unique Key Format

```
{Name}_{ISO2}_{Year}
```

| Field | Description |
|-------|-------------|
| `Name` | Romanized spelling of the baby name, exact as reported |
| `ISO2` | ISO 3166-1 alpha-2 country code, uppercase |
| `Year` | 4-digit year the name held the #1 position |

Examples: `Liam_US_2023` · `Sofia_IT_2022` · `Yui_JP_2021` · `Fatima_EG_2020`

The key is immutable once assigned. It is the monkey's identity across all systems.

### File Naming

```
content/monkeys/{slug}_{YYYYMMDD}.md
```

- `{slug}` = key lowercased, underscores → hyphens: `liam-us-2023`
- `{YYYYMMDD}` = date the post was generated

Explorer display: `Liam_US_2023 20260308.txt`

### Front Matter Schema

```yaml
---
title: "transmission one"
date: 2026-03-08
monkey_key: "Liam_US_2023"      # unique key — REQUIRED
monkey: "Liam"                   # display name
country: "US"                    # ISO2
language: "en"                   # ISO 639-1
source_year: 2023
description: "short teaser"
owner: "gh:username"             # whoever triggered the post
owner_date: "2026-03-08"
token_id: "0x…"                  # keccak256(monkey_key+date+transcript) — content commitment
pq_pubkey: "…"                   # ML-DSA-65 public key — post-quantum ownership anchor
pq_scheme: "ML-DSA-65"          # FIPS 204 / Dilithium3
milestones: []
---
```

### Milestone Tags

| Tag | Meaning |
|-----|---------|
| `first_in_language:{lang}` | First monkey in this language |
| `first_in_country:{iso2}` | First monkey from this country |
| `goal0_complete` | Closes the English Hamlet baseline |
| `goal1_complete` | Closes the all-languages sweep |
| `goal2_complete:{year}` | Closes the year sweep for `{year}` |
| `goal3_complete` | Closes the decade sweep |
| `name_repeat:{prev_key}` | Same name was #1 in a prior year — links to prior entry |
| `data_gap` | Source is non-primary (estimate / proxy / journalistic) |
| `hamlet_fragment` | This transmission contains usable Hamlet material |

---

## Ownership / Mining Mechanic

Each monkey transcript is a unique artifact. The person who triggers a post **owns it**.

### The Unit

A "coin" is one `monkey_key + YYYYMMDD` pair:

```
Liam_US_2023 20260308
```

No two people can own the same coin — once a monkey posts on a given date, that
transcript is taken. A monkey can post on multiple dates; each date is a separate coin.

### How Mining Works

1. A user picks an unclaimed monkey (or date slot on an existing monkey)
2. They trigger the agent → post is generated
3. Their handle/identifier is written into the registry entry and the post's front matter
4. The post page displays their ownership credit

### Registry Fields (to add)

```yaml
owner: "gh:username"        # whoever triggered the post; gh: / email: / etc.
owner_date: "2026-03-08"    # date ownership was claimed
```

### Display

- Post page: small "mined by {owner}" badge
- Leaderboard page (future): ranked by number of posts mined
- Each owner gets a permanent URL: `/monkeys/?owner=username`

### Open Design

- [ ] What is the "value" of a coin? Scarcity (rare languages) vs. volume (popular names)?
- [ ] Can ownership transfer? (Proposed: no — immutable once claimed)
- [ ] Anonymous mining? (Proposed: yes, owner = `anon`)
- [ ] Leaderboard: total posts mined, languages covered, Hamlet fragments found

---

## The Penny Press Machine
*Design TBD — to be spec'd with GF. Notes below are rough intent only.*

Think: the penny smashing machine at a natural history museum. You put in a penny,
pull the knob, watch the gears, and out comes a pressed coin with a unique design.
Your token. Yours forever.

### UI Concept

On the mint/press page:

1. **Machine animation** — illustrated penny press machine, idle state
2. **User picks a monkey** — browse the registry, pick an unclaimed name+date
3. **Pull the knob** — interaction triggers the agent, animation plays (gears spin,
   press descends, coin drops into tray)
4. **Coin drops** — the pressed coin slides out; post is generated and registered
5. **Coin is yours** — displayed immediately in your collection

The knob-pull should feel physical and satisfying. One pull = one coin. No undo.

### The Token (On-Chain)

Each pressed coin is a blockchain token — the monkey transcript as a tradeable artifact.

- **Standard:** ERC-721 NFT (one-of-one per `monkey_key + date`)
- **Metadata:** key, monkey name, country, language, source year, press date, owner
- **Content:** the transcript text is stored in the token metadata (IPFS or on-chain)
- **Wallet:** connect any EVM-compatible wallet (MetaMask, Coinbase Wallet, etc.)
- **Trading:** standard NFT marketplace compatible (OpenSea, etc.)

Token ID = deterministic hash of `monkey_key + YYYYMMDD` — reproducible, no duplication.

### Coin Collection Page (`/collection/`)

Your personal gallery of pressed coins. Reads from connected wallet.

- Grid of coin faces — each coin has a unique design based on monkey metadata
  (language script, country colors, name in native script on the coin face)
- Click a coin → the full transcript
- Filter by: language · country · year · Hamlet fragments
- Share link: `/collection/{wallet-address}`

### Coin Face Design

Each coin is visually unique — generated from the monkey's metadata:

- **Center:** monkey's name in its native script (e.g. يوسف, 유이, Léa)
- **Ring:** country name + year
- **Edge stamp:** `ALMONDFARM.US · INFINITE MONKEY THEOREM`
- **Patina/color:** seeded from `monkey_key` hash — no two coins look the same

*Full visual design to be worked out with GF — this is the fun part.*

### Tech Stack (rough)

- Smart contract: Solidity ERC-721 on an EVM chain (chain TBD — L2 preferred for gas)
- Mint trigger: site calls contract after post is generated
- Frontend: wagmi / viem for wallet connection (or simpler — TBD)
- Collection page: reads wallet NFTs via RPC or indexer

### Open Design (for GF session)

- [ ] Which chain? (Base, Polygon, Arbitrum — low gas, EVM-compatible)
- [ ] Coin art style — hand-drawn? pixel? embossed 3D render?
- [ ] Machine aesthetic — art deco? sci-fi? naturalist museum?
- [ ] Sound design — gear clicks, press thunk, coin clink
- [ ] What happens when you collect a "first in language" coin? Special design?
- [ ] Free to mint? Gas-only? Small fee?
- [ ] Can coins be burned? (destroy transcript = lose ownership forever)

---

## Token Model & Security Design

### Question 1: Real crypto vs. site-native token?

**Option A — Real ERC-721 NFT (on-chain)** ← current plan
- Lives on a public blockchain forever, independent of almondfarm.us
- Tradeable on OpenSea etc., real market value possible
- Gas cost, wallet friction, environmental optics
- The transcript becomes a permanent on-chain artifact

**Option B — Site-native collectible (off-chain)**
- Simpler: a database entry + pretty page, no wallet required
- Lower barrier, but it's just a website record — not really "yours"
- Could still look like a coin, feel like ownership, without crypto

**Option C — Per-language token (fungible layer)**
- Each language family gets its own ERC-20 token: `$ARABIC`, `$MANDARIN`, `$ENGLISH`, etc.
- Pressing a coin in that language earns/burns some of that token
- Rare languages → scarce tokens → actual scarcity economics
- Interesting: Arabic monkeys are rarer → `$ARABIC` is harder to earn

*→ Open: do we want real tradeable value, or just provable ownership?*

---

### Question 2: Quantum Security — Two Separate Layers

The token has two distinct cryptographic layers with different quantum profiles:

| Layer | Mechanism | Quantum safe? | Why |
|-------|-----------|--------------|-----|
| Content integrity | SHA-3/keccak256(monkey_key + date + transcript) → token_id | **Yes** | Grover's gives √ speedup; 256-bit → 128-bit security, still fine |
| Ownership | ETH wallet ECDSA (secp256k1) | **No** | Shor's algorithm can factor the elliptic curve discrete log |

**Note on transcript length:** A longer transcript does not improve quantum security.
Quantum attacks target the signature scheme (ECDSA), not the hash preimage.
Length improves classical brute-force resistance, but that's not the threat model.

#### The real threat: ECDSA wallet signatures

Shor's algorithm on a sufficiently large quantum computer breaks ECDSA entirely.
That's how ETH wallets prove ownership. It is *not* how the token ID is computed.

**The content layer is already safe.** `keccak256(transcript)` as a token ID commitment
is quantum-resistant. No changes needed there.

**The ownership layer needs a plan.** Two options:

---

#### Option 2A — Ride ETH's roadmap (low effort, sound choice)

Ethereum is migrating to post-quantum signatures via account abstraction
(EIP-7560, ERC-4337). When ETH migrates, existing NFTs are automatically covered.
Practical quantum computers that break secp256k1 are 10–20+ years out.
ETH will migrate before then. This is probably fine.

---

#### Option 2B — Embed a PQ keypair at mint time (forward-compatible, elegant) ← chosen approach

At mint time, derive a **CRYSTALS-Dilithium (ML-DSA-65 / FIPS 204)** keypair from
the transcript. Include the public key in the NFT metadata. The owner receives
the secret key privately — it is never stored on the site or on-chain.

```
transcript                     →  SHA-3-256  →  32-byte seed
32-byte seed                   →  ML-DSA-65 KeyGen  →  (pk, sk)
pk (public key)                →  NFT metadata (on-chain + IPFS)
sk (secret key)                →  given to the owner only — never stored
```

**The transcript IS the key.** Literally. SHA-3(transcript) seeds the PQ keypair.
Whoever holds the transcript can rederive the private key and prove PQ ownership.
The coin and its key are the same act of generation.

**What this buys:**
- Right now: provable ownership commitment independent of ECDSA
- When ETH migrates: the ML-DSA public key becomes the authoritative ownership proof
- Always: the transcript's cryptographic value is foregrounded — this is the *point*

**Coin metadata structure:**

```json
{
  "name": "Monkey #42 — Liam / English",
  "monkey_key": "Liam_US_2023",
  "press_date": "2026-03-08",
  "token_id": "0x…keccak256 of key+date+transcript…",
  "transcript_ipfs": "ipfs://Qm…",
  "pq_pubkey": "…ML-DSA-65 public key hex…",
  "pq_scheme": "ML-DSA-65",
  "owner": "gh:username"
}
```

**Post front matter gains two new fields:**

```yaml
token_id: "0x…"          # keccak256 commitment — verifiable, immutable
pq_pubkey: "…"           # ML-DSA-65 public key — PQ ownership anchor
pq_scheme: "ML-DSA-65"   # FIPS 204
```

**Implementation:** `scripts/generate_monkey_post.py` handles all key derivation.
The owner's PQ secret key is printed to stdout at generation time and never stored.

---

### Open Design Questions

- [ ] Which chain? (Base, Polygon, Arbitrum — low gas, EVM-compatible)
- [ ] Per-language fungible token: makes sense economically? Or gimmick?
- [ ] If site-native (no chain): what's the ownership proof mechanism?
- [ ] Can coins be burned? (destroy transcript = lose ownership forever)
- [ ] Minimum transcript length? (Current: 500 words minimum enforced in generation)

---

## Open Questions

- [ ] **Gender** — track #1 male name, #1 female name, or both?
      If both, key format: `Liam_US_2023_M` and `Emma_US_2023_F`.
      Needs decision before Goal 2 begins.

- [ ] **Name ties** — if two names tie for #1, use alphabetically first.
      Always document in registry `source_notes`.

- [ ] **Script support** — posts in Arabic, CJK, Cyrillic, Hebrew, etc.
      The layout likely handles it (UTF-8), but needs a browser check.

- [ ] **Hamlet structure** — how many transmissions per language before we attempt
      assembly? No hard rule yet. Revisit when Goal 1 is close to complete.

---

## Milestones Log

| Date | Milestone | Key |
|------|-----------|-----|
| — | — | — |

---

## Progress

### Goal 1 — Languages

| Language | ISO 639-1 | Primary Country | Key | Done |
|----------|-----------|-----------------|-----|------|
| | | | | |

### Goal 2 — 2023 Country Sweep

| Region | Countries Done | Countries Total | Data Gaps |
|--------|---------------|-----------------|-----------|
| | | | |

### Goal 3 — Decade (2014–2023)

| Year | Done | Remaining |
|------|------|-----------|
| 2023 | 0 | ? |
| 2022 | 0 | ? |
| 2021 | 0 | ? |
| 2020 | 0 | ? |
| 2019 | 0 | ? |
| 2018 | 0 | ? |
| 2017 | 0 | ? |
| 2016 | 0 | ? |
| 2015 | 0 | ? |
| 2014 | 0 | ? |
