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

> **Write Hamlet in every language.**

Not all at once. Not on purpose. One transmission at a time, one monkey at a time,
until every language has enough material to assemble something resembling the play.
The experiment doesn't end — it accumulates.

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

### ☐ Goal 4 — Hamlet in Every Language
Using accumulated transmissions as material, assemble a Hamlet-shaped structure
in each language. This is a curation + composition step, not just generation.
Long-term. The monkeys will get us there.

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
*Ideas to develop — not decided.*

### Question 1: Real crypto vs. site-native token?

**Option A — Real ERC-721 NFT (on-chain)**
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
- The NFT receipt + a fungible language token together
- Interesting: Arabic monkeys are rarer → `$ARABIC` is harder to earn

*→ Open: do we want real tradeable value, or just provable ownership?*

---

### Question 2: Transcript as cryptographic anchor

Each monkey transcript is ~500–2000 words. That's a lot of entropy.

**Idea: the token ID is derived from the content itself, not just the key.**

```
token_id = BLAKE3(monkey_key + date + full_transcript_text)
```

This means:
- Token ID is a commitment to the exact text — tampering with the transcript
  would produce a different hash → the token would no longer match
- The transcript IS the proof of what was generated — immutable by construction
- Anyone can verify: re-hash the content, compare to on-chain token ID

**Why BLAKE3 (or SHA-3) not SHA-256:**
- SHA-256 is vulnerable to Grover's algorithm on quantum computers
  (halves effective key length: 256-bit → 128-bit security)
- BLAKE3 and SHA-3 have better post-quantum resistance profiles
- For a 2000-word transcript: the preimage space is astronomically large —
  even Grover's can't brute-force it; the transcript length is the defense

**Quantum security framing:**
A long transcript is a large preimage. Quantum computers threaten:
- Short hashes (Grover halves bit-security)
- Asymmetric keys like ECDSA (Shor's breaks it entirely)

EVM wallets use ECDSA → *wallets themselves are quantum-vulnerable long-term.*
But the content commitment (transcript → hash) using a long preimage + SHA-3/BLAKE3
is quantum-hard. So the token's content integrity survives even if wallet
signature schemes eventually need upgrading.

**Practical implication:**
The transcript isn't just flavor text — it's the security primitive.
Short transcripts = weaker anchor. Long, dense transcripts = quantum-resistant fingerprint.
This gives us a design reason to make monkey posts *substantive* — longer is more secure.

---

### Open Security Design Questions

- [ ] Hash function choice: BLAKE3 vs. SHA-3 vs. keccak256 (native to EVM)?
- [ ] Store full transcript on IPFS with hash on-chain, or transcript hash only?
- [ ] Wallet sig scheme: ECDSA (current EVM standard, quantum-vulnerable long-term)
      vs. watch for EIP proposals for post-quantum wallet signatures
- [ ] Per-language fungible token: makes sense economically? Or gimmick?
- [ ] If site-native (no chain): what's the ownership proof mechanism?
      Signed JWT? Merkle tree in a public repo?
- [ ] Minimum transcript length for security guarantee? (Flavor rule: 500 words min)

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
