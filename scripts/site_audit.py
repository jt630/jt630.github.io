#!/usr/bin/env python3
"""Build the section table in SITE-MAP.md from the live repo state.

Reads hugo.toml (menu), layouts/index.html (homepage cards), content/,
layouts/ and data/ to answer, per top-level URL section: is it in the
menu, does it have a homepage card, does it have a layout override, does
it use tags, is it covered by a spec doc, and how many inbound links does
its built page get in public/.

Also flags three kinds of drift the hand-maintained docs can't catch on
their own: orphan sections (no menu entry, no card), layout files that
look like dead duplicates of a lookup-order sibling, and data/ files that
nothing in layouts/ or content/ references.

Only the generated table between the SITE-MAP.md markers is rewritten.
Everything else in that file (Known drift, grouping rationale, Hubs) is
hand-maintained and left alone.
"""

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START_MARKER = "<!-- SITE_AUDIT:START -->"
END_MARKER = "<!-- SITE_AUDIT:END -->"

SPEC_DOCS = [
    "MONKEYS.md",
    "PRICE-DISCOVERY.md",
    "THESIS.md",
    "CUNTY-THEME-GUIDE.md",
    "GODDARD.md",
    "DINGER_PALOOZA.md",
    "BEER_SHEET.md",
    "MARKETS.md",
    "docs/AUCTION-MONITORING.md",
    "docs/RECREATION-API.md",
]


def load_menu():
    with open(ROOT / "hugo.toml", "rb") as f:
        toml = tomllib.load(f)
    entries = toml.get("menu", {}).get("main", [])
    items = []
    for e in entries:
        if "url" not in e:
            continue  # a parent header (Build/Taste/Ops), not a leaf
        items.append(
            {
                "name": e["name"],
                "url": e["url"].strip("/"),
                "parent": e.get("parent", ""),
            }
        )
    return items


def load_cards():
    html = (ROOT / "layouts" / "index.html").read_text(encoding="utf-8")
    cards = []
    for m in re.finditer(
        r'<a href="/([^"/]+)/?"\s+class="section-card\s+([^"]+)"', html
    ):
        cards.append({"url": m.group(1), "tone_class": m.group(2)})
    return cards


def content_sections():
    content = ROOT / "content"
    sections = set()
    loose_files = set()
    for p in content.iterdir():
        if p.is_dir():
            sections.add(p.name)
        elif p.suffix == ".md":
            loose_files.add(p.stem)
    return sections, loose_files


def layout_dirs():
    layouts = ROOT / "layouts"
    dirs = set()
    for p in layouts.iterdir():
        if p.is_dir() and p.name not in ("_default", "partials", "page", "taxonomy"):
            dirs.add(p.name)
    # page/*.html are per-URL single-template overrides, keyed by stem
    page_overrides = set()
    page_dir = layouts / "page"
    if page_dir.exists():
        for p in page_dir.glob("*.html"):
            if p.stem != "single":
                page_overrides.add(p.stem)
    return dirs, page_overrides


def find_dead_layout_dupes():
    """Flag a flat `<name>-list.html` / `<name>-single.html` sitting next
    to a subdir `<name>/list.html` / `<name>/single.html` — Hugo's lookup
    order means one of the pair never renders."""
    layouts = ROOT / "layouts"
    dupes = []
    for section_dir in layouts.iterdir():
        if not section_dir.is_dir():
            continue
        flat_names = {p.stem for p in section_dir.glob("*.html")}
        subdirs = {p.name for p in section_dir.iterdir() if p.is_dir()}
        for flat in flat_names:
            for kind in ("list", "single"):
                if flat.endswith(f"-{kind}"):
                    prefix = flat[: -len(f"-{kind}")]
                    if prefix in subdirs and (section_dir / prefix / f"{kind}.html").exists():
                        dupes.append(
                            f"layouts/{section_dir.name}/{flat}.html "
                            f"vs layouts/{section_dir.name}/{prefix}/{kind}.html"
                        )
    return sorted(dupes)


def find_unread_data_files():
    """Data files whose basename (no extension) never appears in
    layouts/ or content/ — a rough but cheap dead-data check."""
    data_dir = ROOT / "data"
    haystack = ""
    for p in list((ROOT / "layouts").rglob("*.html")) + list(
        (ROOT / "content").rglob("*.md")
    ):
        haystack += p.read_text(encoding="utf-8", errors="ignore")

    unread = []
    for p in data_dir.rglob("*.yaml"):
        rel = p.relative_to(data_dir)
        # a nested file is usually addressed by its parent dir name
        # (e.g. data/dinger_palooza/members.yaml -> "dinger_palooza")
        needle = rel.parts[0].replace(".yaml", "")
        if needle not in haystack and p.stem not in haystack:
            unread.append(str(rel).replace("\\", "/"))
    return sorted(unread)


def count_inbound_links(url):
    public = ROOT / "public"
    if not public.exists():
        return None
    # hugo --minify drops quotes on attributes with no special chars, so
    # `href="/apis/"` and `href=/apis/>` both need to match.
    pattern = re.compile(rf'href=["\']?/{re.escape(url)}/["\'>]')
    count = 0
    for p in public.rglob("*.html"):
        count += len(pattern.findall(p.read_text(encoding="utf-8", errors="ignore")))
    return count


def find_spec_doc(url, name):
    """A doc counts as covering a section only if it links the URL
    directly, or names it as a whole word — a bare substring match on
    short common words (e.g. "art", "body") floods every doc with noise."""
    hits = []
    name_pattern = re.compile(rf"\b{re.escape(name.lower())}\b")
    for doc in SPEC_DOCS:
        path = ROOT / doc
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if f"/{url}/" in text or name_pattern.search(text):
            hits.append(doc)
    return hits


def uses_tags(url, sections, loose_files):
    content = ROOT / "content"
    candidates = []
    if url in sections:
        candidates = list((content / url).rglob("*.md"))
    elif url in loose_files:
        candidates = [content / f"{url}.md"]
    for c in candidates:
        if not c.exists():
            continue
        text = c.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"^tags:\s*\[.+\]", text, re.MULTILINE) or re.search(
            r"^tags:\s*$", text, re.MULTILINE
        ):
            return True
    return False


def build_table():
    menu = load_menu()
    cards = load_cards()
    sections, loose_files = content_sections()
    dirs, page_overrides = layout_dirs()

    menu_urls = {m["url"] for m in menu}
    card_urls = {c["url"] for c in cards}
    card_by_url = {c["url"]: c for c in cards}
    all_content_urls = sections | loose_files

    all_urls = sorted(menu_urls | card_urls | all_content_urls)

    rows = []
    orphans = []
    for url in all_urls:
        name = next((m["name"] for m in menu if m["url"] == url), url)
        in_menu = url in menu_urls
        has_card = url in card_urls
        has_layout = url in dirs or url in page_overrides
        has_tags = uses_tags(url, sections, loose_files)
        spec_docs = find_spec_doc(url, name)
        inbound = count_inbound_links(url)

        if not in_menu and not has_card:
            orphans.append(url)

        rows.append(
            {
                "url": url,
                "name": name,
                "in_menu": in_menu,
                "has_card": has_card,
                "has_layout": has_layout,
                "has_tags": has_tags,
                "spec_docs": spec_docs,
                "inbound": inbound,
            }
        )

    return rows, orphans, menu, cards, card_by_url


def render_markdown(rows, orphans, menu, cards, dead_layouts, unread_data):
    lines = []
    lines.append(START_MARKER)
    lines.append("")
    lines.append(
        f"_Generated by `scripts/site_audit.py`. "
        f"{len(menu)} menu items, {len(cards)} homepage cards, "
        f"{len(rows)} distinct sections found across menu/cards/content._"
    )
    lines.append(
        "_Spec doc is a whole-word name match against a fixed doc list — "
        "a heuristic, not proof of coverage. Inbound links counts every "
        "built page in public/ that links `/url/`, including nav/footer, "
        "so a healthy section reads ~90+; near-zero is the orphan signal._"
    )
    lines.append("")
    lines.append("| Section | URL | Menu? | Card? | Layout? | Tags? | Spec doc | Inbound links |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda x: x["url"]):
        check = lambda b: "✔" if b else "—"
        spec = ", ".join(r["spec_docs"]) if r["spec_docs"] else "—"
        inbound = "n/a (no public/)" if r["inbound"] is None else str(r["inbound"])
        lines.append(
            f"| {r['name']} | `/{r['url']}/` | {check(r['in_menu'])} | "
            f"{check(r['has_card'])} | {check(r['has_layout'])} | "
            f"{check(r['has_tags'])} | {spec} | {inbound} |"
        )
    lines.append("")

    if orphans:
        lines.append("**Orphan sections (no menu entry, no homepage card):**")
        for o in orphans:
            lines.append(f"- `/{o}/`")
        lines.append("")

    if dead_layouts:
        lines.append("**Possible dead layout duplicates (lookup-order conflict):**")
        for d in dead_layouts:
            lines.append(f"- {d}")
        lines.append("")

    if unread_data:
        lines.append("**Data files nothing in layouts/ or content/ references:**")
        for d in unread_data:
            lines.append(f"- `data/{d}`")
        lines.append("")

    mismatch = sum(1 for r in rows if r["in_menu"] != r["has_card"])
    lines.append(f"**Menu/card mismatches:** {mismatch}")
    lines.append("")
    lines.append(END_MARKER)
    return "\n".join(lines)


def write_site_map(generated_block):
    path = ROOT / "SITE-MAP.md"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if START_MARKER in text and END_MARKER in text:
            pre = text.split(START_MARKER)[0]
            post = text.split(END_MARKER)[1]
            path.write_text(pre + generated_block + post, encoding="utf-8")
            return
    else:
        text = ""

    scaffold = f"""# Site Map

Audit table below is generated — run `python scripts/site_audit.py` to
refresh it. Everything else on this page is hand-maintained.

{generated_block}

## Known drift

- `content/news.md` has no menu item and no homepage card (see Orphan
  sections above).

## Grouping rationale

(placeholder — filled in during PR-B's Ops split)

## Hubs

(placeholder — filled in during PR-C/PR-D)
"""
    path.write_text(scaffold, encoding="utf-8")


def main():
    rows, orphans, menu, cards, card_by_url = build_table()
    dead_layouts = find_dead_layout_dupes()
    unread_data = find_unread_data_files()

    generated = render_markdown(rows, orphans, menu, cards, dead_layouts, unread_data)
    write_site_map(generated)

    mismatch = sum(1 for r in rows if r["in_menu"] != r["has_card"])
    print(f"SITE-MAP.md updated: {len(rows)} sections, {mismatch} menu/card mismatches, "
          f"{len(orphans)} orphans, {len(dead_layouts)} dead-layout dupes, "
          f"{len(unread_data)} unread data files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
