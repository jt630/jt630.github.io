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

### Hamlet Detection (First-Party)

After each coin is minted, the transcript is scanned for **n-gram matches** against
the known Hamlet text in that language. Matching sequences (contiguous word runs that
appear in Hamlet) are tagged as fragments.

- **Fragment:** a contiguous run of N words that matches Hamlet (minimum N = TBD)
- **Completion:** a language is "done" when every contiguous N-word chunk of Hamlet
  has been found across all transmissions in that language
- Detection can be re-run as methods improve — coins are permanent, scanning isn't

**Hamlet is the only first-party scan.** We look for Hamlet because that's the north
star — the shutdown condition. Everything else the transcripts might contain (poetry,
proverbs, phrases, word patterns, name sequences) is not our problem to find. The
transcripts are public. Anyone can scan them for anything. If someone wants to search
every Māori coin for traditional proverbs, or find love poems in the French monkey's
output, that's their project built on our raw material.

Think of it like a fortune cookie: nobody buys the cookie. The cookie is terrible.
But when it's sitting there after the meal, everyone cracks it open. The quarter
covers the crack. Hamlet is our fortune. Everything else is someone else's fortune
to find.

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

Each monkey is identified by its **ISO 639-1 language code** and a **baby name** —
the most popular given name in its primary country for the year the monkey was
registered.

```
Liam (en) · Yui (ja) · Mohammed (ar) · Sofía (es) · 伟 (zh) · Aarav (hi) …
```

One monkey per language. The language code is the system identifier; the name is the
face. The name appears on every coin, on the registry page, and in the penny press UI.

**Why baby names:**
- They give each monkey a face. A registry of language codes is a spreadsheet.
  A registry of Liam, Yui, Mohammed, Sofía is a room full of monkeys.
- Baby names are themselves a cultural artifact — the most popular name in a
  country reflects that moment in that culture. The monkeys carry that.
- Names make the coins personal. Pulling a coin from "Yui" is different from
  pulling a coin from `ja`. People will trade for coins that carry their name,
  their kid's name, a name that means something to them.
- Over time, the full registry becomes a snapshot of global naming culture
  at the moment each monkey was born.

**Name selection rules:**
1. Use the **#1 most popular baby name** in the monkey's primary country
   for the year the monkey is first registered
2. Source: official national statistics where available, otherwise best
   available data (UN, SSA, national registries)
3. Use the name in its **native script** (العربية not "Mohammed" on the `ar` monkey)
   with a romanized form available for display contexts that need it
4. If two languages share a country, use the most popular name in that
   language's speaking population, not the national aggregate
5. Names are permanent once assigned — they don't change if popularity shifts

### Name Trading

Names are what make coins personal and tradeable beyond pure collection:

- **"Find your name"** — search the registry for your name or a name you love.
  Every coin minted by that monkey carries the name. Trade for it, collect it.
- **"My name, my coin"** — someone named Liam might want every Liam coin.
  Someone named Yui might want the first Yui coin ever minted.
- **Name-specific milestones** — `first_in_language` coins are extra meaningful
  because they're the first coin a named monkey ever produced.
- **Cultural preservation** — the registry preserves the most popular name in
  ~184 cultures at a specific moment in time. The names themselves are an archive.

This doesn't require smart contracts or a trading platform yet. It starts with
display: showing the name prominently on every coin, making the registry browsable
by name, and letting the community figure out what names are worth to them.

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
title: "Liam — transmission 042"
date: 2026-03-10
monkey_name: "Liam"              # baby name — the monkey's face
monkey_name_native: "Liam"       # name in native script (same for Latin langs)
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

### Pricing

$0.25 per coin. A quarter. Gumball price. Pressed-penny price.

This is not a business model. This is a souvenir price. The project will be net
negative on money and net positive on having built something genuinely weird. The
quarter covers the crack of the fortune cookie. Nobody's getting rich. The machine
exists because people want to pull the lever.

### Open Design

- [ ] Can ownership transfer? (Proposed: no — immutable once claimed)
- [ ] Anonymous mining? (Proposed: yes, owner = `anon`)
- [ ] Leaderboard: total coins minted, languages covered, Hamlet fragments found
- [ ] Payment integration — Stripe? crypto? honor system?

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

## The Archive

When the monkeys finish — if they finish — the site becomes a permanent record of
three things simultaneously:

1. **A library of word combinations** — every transmission is a unique sequence of
   words in a specific language. Millions of coins across ~184 languages produce an
   enormous corpus of random word combinations. Most are noise. Some contain Hamlet
   fragments. All of them are real words in real languages, preserved exactly as the
   dictionary contained them.

2. **A language preservation layer** — for languages with shrinking speaker populations,
   the monkey's dictionary IS the record. The Swahili monkey, the Welsh monkey, the
   Māori monkey — their dictionaries and their transmissions preserve vocabulary that
   might otherwise exist only in academic databases. Every coin minted in a minority
   language is an act of preservation, even if the content is random.

3. **A naming culture snapshot** — the registry captures the most popular baby name
   in ~184 cultures at a specific moment in time. Names reflect immigration patterns,
   pop culture, religious traditions, political shifts. Liam dominates the Anglosphere.
   Mohammed spans the Arabic-speaking world. Sofía crosses all of Latin America. The
   names the monkeys carry are themselves an artifact — a global census of what parents
   were naming their children when the experiment began.

The monkeys aren't just trying to write Hamlet. They're inadvertently building an
archive of human language and naming culture, one coin at a time.

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
  monkey_name: "Liam"             # most popular baby name (US, 2026)
  monkey_name_native: "Liam"      # in native script
  name_source: "SSA"              # Social Security Administration
  name_year: 2026                 # year the name was sourced
  country: "US"                   # primary country for this language
  script: "Latin"
  dictionary_source: "aspell-en"
  dictionary_size: 50000
  total_coins: 0
  first_coin_date: null
  hamlet_progress: 0.0
  milestones: []

- language: "ja"
  language_name: "Japanese"
  monkey_name: "Yui"
  monkey_name_native: "結衣"
  name_source: "meiji-yasuda"
  name_year: 2026
  country: "JP"
  script: "CJK"
  dictionary_source: "mecab-ipadic"
  dictionary_size: 120000
  total_coins: 0
  first_coin_date: null
  hamlet_progress: 0.0
  milestones: []

- language: "ar"
  language_name: "Arabic"
  monkey_name: "Mohammed"
  monkey_name_native: "محمّد"
  name_source: "babycenter-mena"
  name_year: 2026
  country: "SA"
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

---

## Build Plan — Session Task Lists

Ordered by dependency. Each block is one Sonnet session's worth of work.
Copy a block into a session and go.

**Before every session:** Read `MONKEYS.md` and `CLAUDE.md` first. They contain
design decisions and conventions that prevent you from reinventing or contradicting
prior work.

---

### Session 1: English Dictionary + First Coin

**Goal:** Mint the first coin. Prove the pipeline end-to-end.

**Context for Sonnet:** This session creates the core generation pipeline that
every future session depends on. The front matter schema in MONKEYS.md is the
contract — match it exactly. Don't add fields, don't rename fields.

- [ ] Source English dictionary — download aspell-en word list, clean it,
      save to `data/dictionaries/en.txt` (one word per line, lowercase, deduped)
- [ ] Build `scripts/generate_monkey_post.py` — the mint script:
  - Read dictionary from `data/dictionaries/{lang}.txt`
  - Perform uniform random walk (sample N words with replacement)
  - Write output to `content/monkeys/{lang}_{YYYYMMDD}.md` with full front matter
  - Front matter **must match the schema in MONKEYS.md exactly** — read it first
  - Update `data/monkey_registry.yaml` (increment `total_coins`, set `first_coin_date`)
  - Word count: 5,000 words per transmission (configurable via CLI arg)
  - No Hamlet scanning yet — just the walk
  - Accept `--lang`, `--words`, `--owner` as CLI args (defaults: en, 5000, anon)
- [ ] Register the English monkey in `data/monkey_registry.yaml`:
  ```
  language: en, monkey_name: Liam, country: US, etc.
  ```
  Follow the Registry Schema section in MONKEYS.md for all fields.
- [ ] Run the script — mint `en_{today}.md`
- [ ] Verify: `hugo --minify` builds cleanly with the new coin
- [ ] Verify: `hugo server` renders the coin at `/monkeys/en_{date}/`
- [ ] Create `.claude/commands/mint.md` — a slash command that prompts for
      language and word count, then runs `generate_monkey_post.py`.
      See `/new-post` in `.claude/commands/new-post.md` for the pattern.

**Learning opportunity:** Creating the `/mint` slash command teaches you how
custom commands work. They're markdown files in `.claude/commands/` that become
interactive prompts. After this session, minting is one command instead of
remembering script paths and flags.

---

### Session 2: Hamlet Scanner

**Goal:** Build the Hamlet n-gram detection system.

**Context for Sonnet:** Hamlet scanning is the ONLY first-party detection we do.
See the "Hamlet Detection (First-Party)" section in MONKEYS.md for the philosophy.
Everything else (poetry, proverbs, patterns) is community territory. Don't scope
creep into general text analysis.

- [ ] Source Hamlet text — find a clean plaintext English Hamlet,
      save to `data/hamlet/en.txt` (words only, lowercased, one continuous sequence)
- [ ] Build `scripts/hamlet_scan.py`:
  - Load Hamlet text as word list
  - Load a coin's transcript as word list (parse the markdown, extract body text)
  - Scan for contiguous n-gram matches (configurable minimum n, start with n=3)
  - Output: list of matched fragments with position and length
  - Update coin front matter: `hamlet_fragments`, `longest_fragment`
  - Accept `--coin` (path to coin .md) or `--lang` (scan all coins for a language)
- [ ] Run against the first English coin — record results (expect: almost nothing)
- [ ] Add cumulative Hamlet progress tracking:
  - Which Hamlet n-grams have been found across ALL coins for a language?
  - Update `hamlet_progress` in registry (percentage of unique Hamlet n-grams covered)
- [ ] Integration: update `generate_monkey_post.py` to optionally run Hamlet scan
      after minting (flag: `--scan`). Keep them separate scripts but wire them together.

**Learning opportunity:** The scan script should be idempotent — running it twice
on the same coin produces the same result. This is important because MONKEYS.md
says "Detection can be re-run as methods improve — coins are permanent, scanning
isn't." Design for re-scanning from the start.

---

### Session 3: Multi-Language Expansion

**Goal:** Register 10+ monkeys and mint first coins.

**Context for Sonnet:** This is a research-heavy session. Use **parallel Agent
calls** for independent lookups — don't search baby names one country at a time.
Launch 10 research agents simultaneously. This is faster and is how Claude Code
is meant to handle bulk research.

- [ ] **Use parallel agents** to research simultaneously:
  - Dictionary sources for: `es`, `fr`, `de`, `pt`, `ja`, `ar`, `zh`, `hi`, `ko`, `sw`
  - #1 baby name for each language's primary country (2025/2026 data)
  - Launch these as independent Agent calls in a single message
- [ ] Download/generate dictionaries, save each to `data/dictionaries/{lang}.txt`
  - Same format as English: one word per line, lowercase, deduped
  - Record `dictionary_source` and `dictionary_size` for registry
- [ ] Register all monkeys in `data/monkey_registry.yaml`
  - Follow the schema exactly — check `monkey_name_native` uses native script
  - Verify YAML is valid after editing
- [ ] Batch mint: one coin per language using `generate_monkey_post.py`
- [ ] `hugo --minify` — verify all coins build cleanly
- [ ] Spot-check non-Latin scripts in browser: Arabic (RTL), CJK, Devanagari
- [ ] Commit dictionaries and registry together, coins separately
  (dictionaries are infrastructure, coins are content — keep the history clean)

**Learning opportunity:** Parallel agents. When you have N independent research
tasks, you can launch N agents in one message. Each runs its own search. You get
all results back without sequential waiting. Use this pattern any time you need
to look up multiple independent things.

---

### Session 4: Coin Display & Single Page

**Goal:** Make individual coin pages look good.

**Context for Sonnet:** Use `isolation: "worktree"` for the CSS/layout work.
This gives you a throwaway copy of the repo to experiment in. If the design
works, merge it. If not, discard — no risk to the main branch. The site's theme
is documented in `CUNTY-THEME-GUIDE.md` — read it for colors and conventions.

- [ ] Read `CUNTY-THEME-GUIDE.md` for the site's color palette and component style
- [ ] Read existing layouts: `layouts/_default/single.html`, `layouts/_default/list.html`
      to understand the current patterns before creating new ones
- [ ] Create `layouts/monkeys/single.html`:
  - Monkey name + native name prominently displayed
  - Language, transmission number, date
  - "Mined by {owner}" badge
  - Coin key displayed
  - Hamlet fragment count (if any)
  - The transcript itself — full wall of text, styled as monospace/typewriter
- [ ] Coin face visual — CSS-only coin design:
  - Circle with language name in native script centered
  - ISO code + transmission number on the ring
  - `ALMONDFARM.US · INFINITE MONKEY THEOREM` edge text
  - Color/patina seeded from coin_key hash (CSS `hsl()` from hash)
- [ ] Add CSS to `assets/css/main.css` — don't create a new stylesheet.
      This project uses a single CSS file (see CLAUDE.md).
- [ ] Mobile-responsive check — test at 375px width
- [ ] `hugo --minify` — verify build

**Learning opportunity:** Worktree isolation. When experimenting with layouts
and CSS, use `isolation: "worktree"` on Agent calls. You get a full copy of the
repo to break without consequences. This is how you prototype safely.

---

### Session 5: Registry & Browse Page

**Goal:** Make the monkey registry browsable.

**Context for Sonnet:** The registry page reads from `data/monkey_registry.yaml`.
Hugo's data templates (`{{ site.Data.monkey_registry }}`) make this straightforward.
The "Find your name" search should be vanilla JS — this project has no JS framework
(see CLAUDE.md: "Vanilla JS — only a hamburger menu toggle").

- [ ] Build `layouts/monkeys/list.html` (the section list page):
  - Grid/table of all registered monkeys from `data/monkey_registry.yaml`
  - Each entry shows: name (native), language, country flag emoji, total coins, hamlet progress
  - Vanilla JS filter/search by name — no frameworks, no npm
  - Sort by name, language, coin count (JS click handlers on column headers)
- [ ] Add stats dashboard at top:
  - Total monkeys registered (count entries in registry)
  - Total coins minted (sum `total_coins` across registry)
  - Overall Hamlet progress (average `hamlet_progress`)
  - Goal 0 / Goal 1 status bars
- [ ] Link list of individual coins below the registry (existing Hugo list behavior)
- [ ] Add "Monkeys" to nav in `hugo.toml` menu config + `layouts/_default/baseof.html`
- [ ] `hugo --minify` — verify build

---

### Session 6: Crypto Layer

**Goal:** Add content integrity hashing to each coin.

**Context for Sonnet:** The crypto design is in MONKEYS.md under "Token & Crypto
Layer." Read it. keccak256 is the priority. ML-DSA-65 is nice-to-have — if the
Python deps aren't available in this environment, stub the function and move on.
Don't spend the session fighting package installs.

- [ ] Add keccak256 hashing to `generate_monkey_post.py`:
  - `token_id = keccak256(coin_key + transcript)`
  - Use `pycryptodome` or `pysha3` — check what's available first
  - Write `token_id` to front matter
- [ ] Add ML-DSA-65 keypair generation:
  - Check if `oqs` or `dilithium` Python package is available
  - If yes: `SHA-3-256(transcript) → seed → ML-DSA-65 KeyGen → (pub, secret)`
  - Store `pq_pubkey` in front matter, print `secret_key` to stdout (NEVER stored)
  - **If deps unavailable: stub with a TODO comment and move on.** Don't block.
- [ ] Display `token_id` on coin single page (`layouts/monkeys/single.html`)
- [ ] Build `scripts/backfill_tokens.py` — re-run on all existing coins to add token_ids
- [ ] Run backfill, verify front matter updated, `hugo --minify`

---

### Session 7: Penny Press UI

**Goal:** Interactive mint page. Design session — build with GF.

**Context for Sonnet:** This is a creative/design session. The press is the public
face of the project. Read the "Penny Press Machine" section in MONKEYS.md for the
vision. All JS should be vanilla — no frameworks. All CSS goes in `assets/css/main.css`.
Use `CUNTY-THEME-GUIDE.md` for the color palette.

- [ ] Read MONKEYS.md "Penny Press Machine" section + CUNTY-THEME-GUIDE.md
- [ ] Create `content/press.md` + `layouts/press/single.html`
  (or use `layouts/_default/` with a custom type — match existing patterns)
- [ ] Machine idle state — CSS illustration of a penny press
- [ ] Language picker — dropdown or grid of available monkeys from registry data
- [ ] Pull animation — CSS/JS sequence (knob pull → gears spin → coin drops)
  - Pure CSS transitions + vanilla JS state machine
  - No animation libraries
- [ ] Result display — show the minted coin face + first few words of transcript
- [ ] Link to full coin page
- [ ] Add "Press" to site nav
- [ ] `hugo --minify` — verify build

---

### Session 8: Automation & Scaling

**Goal:** Make minting automatic or semi-automatic.

**Context for Sonnet:** GitHub Actions workflow goes in `.github/workflows/`.
There's already a `deploy.yml` there — read it first to understand the existing
CI/CD pattern. The daily mint workflow should be a SEPARATE file, not modifications
to the deploy workflow.

- [ ] Read `.github/workflows/deploy.yml` to understand the existing CI pattern
- [ ] Create `.github/workflows/daily-mint.yml`:
  - Schedule: `cron: '0 12 * * *'` (noon UTC daily)
  - Pick a random language from registry (or round-robin)
  - Install Python + deps, run generation script
  - `hugo --minify` to verify build
  - Commit + push the new coin
  - Owner = `anon` for automated mints
- [ ] Build batch mint wrapper: `scripts/batch_mint.py`
  - Mint N coins across M languages in one run
  - Accept `--languages all` or `--languages en,fr,de`
  - Accept `--count N` (coins per language)
- [ ] Storage audit: estimate GitHub Pages limits at scale
  - 5,000 words x ~6 chars avg = ~30KB per coin
  - 184 languages x 365 days = 67,160 coins/year = ~2GB/year
  - Document findings in MONKEYS.md under a new "Scaling Notes" section
  - If limits are a concern, propose alternatives (separate repo for transcripts,
    external storage, pagination)
