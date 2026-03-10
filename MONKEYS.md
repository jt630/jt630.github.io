# Infinite Monkey Theorem — Project Plan

## Summary

We are running the infinite monkey theorem simultaneously in every human language.

There is **one monkey per language**. When a monkey types, it performs a **brownian
walk through its language's full dictionary** — word by word, no grammar, no intent,
pure noise.

Each mint produces a massive wall of random words in that language. Given enough
transmissions, the monkeys will collectively produce Hamlet in every language — not
by writing it, but by wandering through the possibility space until the text appears.

These are the transcripts so far.

Registry: `data/monkey_registry.yaml`

---

## The North Star

> **Produce Hamlet in every language available to computers. Then shut down.**

Not on purpose. One coin at a time, one monkey at a time. Each coin is a brownian
walk — thousands of words sampled from a language's dictionary, laid end to end.
Somewhere in the noise, Hamlet fragments appear. When every language has produced
enough material to assemble the complete play, the experiment closes. The monkeys
go quiet. The site becomes a permanent archive.

This is a countdown, not an infinite feed. The end condition is baked in.

### What the monkeys are actually making

Each transmission is a **random walk through a dictionary**. The monkey picks words
from the full vocabulary of its language — not sentences, not prose, not meaning.
Just words. One after another. A massive, dense, unique sequence.

The walk is the point. Inside the noise, Hamlet hides. The monkeys aren't trying to
write it. They're generating enough randomness that it *must* eventually appear —
the same way the original thought experiment works, but at word scale instead of
character scale, and in every human language simultaneously.

Each transmission is also a cryptographic artifact — the random text seeds a
quantum-resistant hash. The monkeys aren't just typing; they're generating
irreducible entropy. The goal and the security mechanism are the same thing:
**walk through enough words in enough languages and you've also generated a
complete set of language-diverse quantum-secure keys.**

When every language finishes — the keys exist, Hamlet exists, the machine stops.

---

## How a Transmission Works

A transmission is **not** AI-generated prose. It is a programmatic random walk:

1. Load the **full dictionary** for the monkey's language
2. Sample words — the walk method produces a sequence of dictionary words
3. Output is a wall of text: thousands of words, no punctuation, no grammar
4. The length of each transmission may vary (open — may evolve over time)

### Example (English, ~50 words shown of thousands)

```
blanket survey infinite cloud perplex roam thistle quarter velocity
moss amber translate furnish orchard peculiar wander digest throne
marble scaffold petition ghost remedy sovereign curtain dissolve
trumpet occasion virtue corrupt minister occasion funeral trumpet
ceremony poison kingdom avenge father remember
```

No sentences. No intent. Just a walk through English. But notice — buried in there,
"ghost," "poison," "kingdom," "avenge," "father," "remember." Hamlet is in the
dictionary. The walk will find it.

### Hamlet Detection

After each coin is minted, the transcript is scanned for **n-gram matches** against
the known Hamlet text in that language. Matching sequences (contiguous word runs that
appear in Hamlet) are tagged as fragments.

- **Fragment:** a contiguous run of N words that matches Hamlet (minimum N = TBD)
- **Completion:** a language is "done" when every contiguous N-word chunk of Hamlet
  has been found across all transmissions in that language
- Detection can be re-run as methods improve — coins are permanent, scanning isn't

### What "Enough" Means

This is genuinely hard. A true random walk at word level through a full dictionary
will almost never produce long contiguous Hamlet sequences by pure chance. The math
is brutal — even a 5-word match is astronomically unlikely with uniform random
sampling from a large dictionary.

This is an honest tension in the project. Options:

1. **Accept the impossibility** — the experiment is conceptual/artistic. "Completion"
   is asymptotic. The monkeys type forever and never finish. The countdown never
   reaches zero. That's the point.
2. **Lower the bar** — define completion as thematic coverage, not literal text match.
   Less pure but achievable.
3. **Weight the walk** — bias the dictionary sampling toward Hamlet's vocabulary
   (frequency-weighted or Markov chain). Makes fragments more likely but less random.
4. **Redefine the unit** — match at the word level (individual words from Hamlet
   appearing in sequence, not necessarily contiguous) rather than exact n-grams.

**This is an open question. It doesn't need to be resolved now.** The monkeys can
start typing before we know exactly how they finish.

---

## Goals (ordered)

### ☐ Goal 0 — Hamlet in English first
Before expanding outward: mint enough English coins to understand the statistics.
How often do Hamlet words cluster? What does fragment detection look like in practice?
This proves the format and gives a baseline.

---

### ☐ Goal 1 — First Coin in Every Language
One transmission from every language with a digital dictionary available
(target: all ISO 639-1 languages with a living speaker population — ~184 languages).

Each coin is a walk through that language's dictionary.

**How:**
1. Source or build a dictionary for the target language
2. Mint the coin → generates one walk in that language
3. Register the entry; tag `first_in_language:{lang}`

**Milestone:** `goal1_complete` — tagged on the final entry that closes the language set.

---

### ☐ Goal 2 — Hamlet in Every Language → Shutdown

When accumulated transmissions contain enough material to assemble Hamlet in
every language — the experiment ends.

The site does not get a new section. No new monkeys are registered. The machine
stops. Everything that exists at that moment is the permanent archive: every
transcript, every coin, every key, every language's Hamlet.

The scope is defined by what computers can encode: every language with a Unicode
block and a living or historical writing system. That's the finish line.

**Shutdown condition:** `hamlet_complete` tagged in every language in the registry.
The site enters read-only mode. The penny press goes cold. The coins remain.

---

## Generation Architecture

Each monkey is **one entry per language** in the registry. When a coin is minted
for the English monkey (`en`), the system:

1. Reads `data/monkey_registry.yaml` → finds the `en` entry
2. Loads the **dictionary** for that language
3. Performs a random walk — sampling words from the dictionary
4. Output = a "transmission" — a massive wall of random words, no editing
5. Saves to `content/monkeys/en_{YYYYMMDD}.md` with full front matter
6. Scans the output for Hamlet n-gram fragments, tags any matches
7. Updates the registry entry (`total_coins`, any new milestones)

**Generation triggers:** manual (CLI) or scripted batch sweep.
The generation script lives at: `scripts/generate_monkey_post.py` *(to be built)*

### Dictionary Sources

Each language needs a word list. Sources (in priority order):
- Aspell/Hunspell dictionaries (open source, wide language coverage)
- Wiktionary frequency lists
- NLTK / spaCy word lists
- Custom compiled from Hamlet translations + general corpora

Dictionary files stored at: `data/dictionaries/` *(to be built)*

### Walk Method

**Current plan:** to be determined. Options ranked by purity:

| Method | Description | Hamlet fragment likelihood |
|--------|-------------|--------------------------|
| Uniform random | Each word sampled independently from full dictionary | Lowest (purest) |
| Frequency-weighted | Common words appear more often, matching natural language distribution | Low-medium |
| Markov chain | Next word influenced by previous word(s) | Medium (local texture) |
| Hamlet-weighted | Hamlet vocabulary overrepresented in the sampling pool | Higher (less pure) |

The walk method may evolve over time. Early coins might use one method; later coins
another. The method used is recorded in each coin's front matter for transparency.

---

## Key Design

### Monkey Identity

Each monkey is identified by its **ISO 639-1 language code**:

```
en · ar · ja · es · zh · hi · sw · ko · ru · de · fr …
```

One monkey per language. The language code is the monkey's identity across all systems.

### Coin Key Format

A coin is one mint from one monkey on one date:

```
{lang}_{YYYYMMDD}
```

Examples: `en_20260310` · `ar_20260310` · `ja_20260311` · `es_20260312`

### File Naming

```
content/monkeys/{lang}_{YYYYMMDD}.md
```

Examples: `content/monkeys/en_20260310.md` · `content/monkeys/ar_20260310.md`

### Front Matter Schema

```yaml
---
title: "en — transmission 042"
date: 2026-03-10
language: "en"                   # ISO 639-1 — the monkey's identity
language_name: "English"         # human-readable
coin_key: "en_20260310"          # unique coin identifier
transmission_number: 42          # sequential per language
word_count: 5000                 # total words in this transmission
walk_method: "uniform"           # how words were sampled
dictionary_size: 50000           # number of words in the source dictionary
owner: "gh:username"             # whoever triggered the mint
owner_date: "2026-03-10"
hamlet_fragments: 0              # number of n-gram matches found
longest_fragment: 0              # longest contiguous Hamlet match (in words)
token_id: ""                     # keccak256(coin_key+transcript) — future
pq_pubkey: ""                    # ML-DSA-65 public key — future
pq_scheme: ""                    # FIPS 204 / Dilithium3 — future
milestones: []
---
```

### Milestone Tags

| Tag | Meaning |
|-----|---------|
| `first_in_language:{lang}` | First coin ever minted in this language |
| `goal0_complete` | Closes the English Hamlet baseline |
| `goal1_complete` | Closes the all-languages sweep |
| `hamlet_fragment` | This transmission contains a Hamlet match |
| `hamlet_complete:{lang}` | This language has produced enough to assemble Hamlet |

---

## Ownership / Mining Mechanic

Each coin is a unique artifact. The person who triggers a mint **owns it**.

### The Unit

A "coin" is one `lang + YYYYMMDD` pair:

```
en_20260310
```

No two people can own the same coin — once a monkey mints on a given date, that
transcript is taken. A monkey can mint on multiple dates; each date is a separate coin.

### How Mining Works

1. A user picks a language (or gets one assigned)
2. They pull the press → the walk runs, words are generated
3. Their handle is written into the coin's front matter
4. The post page displays their ownership credit

### Display

- Post page: small "mined by {owner}" badge
- Leaderboard page (future): ranked by number of coins mined
- Each owner gets a permanent URL: `/monkeys/?owner=username`

### Open Design

- [ ] What is the "value" of a coin? Scarcity (rare languages) vs. volume?
- [ ] Can ownership transfer? (Proposed: no — immutable once claimed)
- [ ] Anonymous mining? (Proposed: yes, owner = `anon`)
- [ ] Leaderboard: total coins minted, languages covered, Hamlet fragments found

---

## The Penny Press Machine
*Design TBD — to be spec'd with GF. Notes below are rough intent only.*

Think: the penny smashing machine at a natural history museum. You put in a penny,
pull the knob, watch the gears, and out comes a pressed coin with a unique design.
Your token. Yours forever.

### UI Concept

On the mint/press page:

1. **Machine animation** — illustrated penny press machine, idle state
2. **User picks a language** — browse the registry, pick a language to mint
3. **Pull the knob** — interaction triggers the walk, animation plays (gears spin,
   press descends, coin drops into tray)
4. **Coin drops** — the pressed coin slides out; words are generated and registered
5. **Coin is yours** — displayed immediately in your collection

The knob-pull should feel physical and satisfying. One pull = one coin. No undo.

### Coin Face Design

Each coin is visually unique — generated from the language metadata:

- **Center:** the language's name in its own script (e.g. العربية, 日本語, English)
- **Ring:** ISO code + transmission number
- **Edge stamp:** `ALMONDFARM.US · INFINITE MONKEY THEOREM`
- **Patina/color:** seeded from `coin_key` hash — no two coins look the same

*Full visual design to be worked out with GF — this is the fun part.*

### Open Design (for GF session)

- [ ] Coin art style — hand-drawn? pixel? embossed 3D render?
- [ ] Machine aesthetic — art deco? sci-fi? naturalist museum?
- [ ] Sound design — gear clicks, press thunk, coin clink
- [ ] What happens when you collect a "first in language" coin? Special design?

---

## Token & Crypto Layer (Design Phase — Low Priority)

The crypto layer is designed but not yet implemented. It adds three things:

1. **Content integrity** — hash commitment proving the transcript hasn't been altered
2. **Ownership proof** — quantum-resistant keypair derived from the transcript itself
3. **On-chain permanence** — optional NFT minting for tradeable ownership

### Content Integrity (keccak256)

```
token_id = keccak256(coin_key + transcript)
```

This is quantum-safe (Grover's gives √ speedup; 256-bit → 128-bit post-quantum
security, still solid). The token ID is a deterministic fingerprint of the coin.

### Quantum Ownership (ML-DSA-65)

At mint time, derive a **CRYSTALS-Dilithium (ML-DSA-65 / FIPS 204)** keypair from
the transcript:

```
transcript  →  SHA-3-256  →  32-byte seed
seed        →  ML-DSA-65 KeyGen  →  (public_key, secret_key)
public_key  →  stored in coin metadata (front matter / on-chain)
secret_key  →  given to owner at mint time — NEVER stored
```

**The transcript IS the key.** SHA-3(transcript) seeds the PQ keypair. Whoever holds
the transcript can rederive the private key and prove ownership. The coin and its key
are the same act of generation.

### On-Chain (Future)

- **Standard:** ERC-721 NFT (one-of-one per coin key)
- **Chain:** TBD (L2 preferred — Base, Polygon, or Arbitrum)
- **Wallet:** EVM-compatible (MetaMask, Coinbase Wallet, etc.)
- **Content:** transcript stored on IPFS, referenced in token metadata

### Open Crypto Questions

- [ ] Which chain? (Base, Polygon, Arbitrum — low gas, EVM-compatible)
- [ ] Real ERC-721 NFT, site-native token, or per-language fungible tokens?
- [ ] Free to mint? Gas-only? Small fee?
- [ ] Can coins be burned? (destroy transcript = lose ownership forever)
- [ ] When to implement? (After generation pipeline is stable)

---

## Open Questions

- [ ] **Script support** — posts in Arabic, CJK, Cyrillic, Hebrew, etc.
      The layout likely handles it (UTF-8), but needs a browser check.
      Dictionary sourcing for non-Latin scripts is the real challenge.

- [ ] **Transmission length** — how many words per coin? Fixed? Variable?
      May evolve over time. Record `word_count` in front matter regardless.

- [ ] **Walk method** — uniform random, frequency-weighted, Markov, or
      Hamlet-weighted? See Walk Method table above. May evolve.

- [ ] **Hamlet completion definition** — exact n-gram match vs. thematic
      coverage vs. word-level (non-contiguous) matching. See "What Enough
      Means" section. Doesn't block generation.

- [ ] **Dictionary curation** — who builds/maintains the word lists?
      How do we handle languages with limited digital dictionary resources?

- [ ] **Multiple coins per day?** — current key is `lang_YYYYMMDD`, limiting
      to one coin per language per day. Enough? Or add a sequence number?

---

## Registry Schema

`data/monkey_registry.yaml` — one entry per language:

```yaml
- language: "en"
  language_name: "English"
  script: "Latin"
  dictionary_source: "aspell-en"
  dictionary_size: 50000
  total_coins: 0
  first_coin_date: null
  hamlet_progress: 0.0          # percentage of Hamlet fragments found
  milestones: []

- language: "ar"
  language_name: "Arabic"
  script: "Arabic"
  dictionary_source: "aspell-ar"
  dictionary_size: 40000
  total_coins: 0
  first_coin_date: null
  hamlet_progress: 0.0
  milestones: []
```

---

## Milestones Log

| Date | Milestone | Language |
|------|-----------|----------|
| — | — | — |

---

## Progress

### Goal 0 — English Baseline

| Coins Minted | Hamlet Fragments Found | Longest Fragment |
|-------------|----------------------|-----------------|
| 0 | 0 | 0 words |

### Goal 1 — All Languages

| Languages with ≥1 Coin | Total Languages | Coverage |
|------------------------|----------------|----------|
| 0 | ~184 | 0% |
