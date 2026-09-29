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

# Sections that are intentionally outside the main menu — linked from
# somewhere else on purpose (e.g. hubs/ is reachable via the homepage
# Connections strip, not the nav; about is reachable via the footer
# contributor links) — so a missing menu entry there isn't drift and
# shouldn't be flagged as an orphan.
NON_MENU_SECTIONS = {"hubs", "about"}


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
    """Homepage cards are data-driven (layouts/index.html loops over the
    menu), so there's no static template markup to grep for a card list
    any more. Read the built public/index.html instead — a menu leaf that
    doesn't render a card there is the real signal. If public/ doesn't
    exist, fall back to treating every menu leaf as a card, since that's
    what the loop template guarantees."""
    public_index = ROOT / "public" / "index.html"
    if not public_index.exists():
        return None  # caller falls back to "every menu leaf has a card"

    html = public_index.read_text(encoding="utf-8")
    cards = []
    for m in re.finditer(
        r'href=["\']?/([^"\'/>]+)/["\']?\s+class=["\']?section-card\s+([^"\'>]+)["\']?',
        html,
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
    """Data files with no detectable reader, checked three ways:

    1. Hugo template access — `Data.<name>` in layouts/ or content/. Strict
       on purpose: an earlier version matched a bare substring/word on the
       name and was fooled by unrelated prose ("cooking/ recipes that go
       off" in layouts/brain/list.html falsely cleared
       data/recipes/staples.yaml, which no template actually loads).
    2. Script/doc access — the file's path relative to data/ appearing in
       scripts/, docs/, .claude/commands/, root-level *.md, or the GitHub
       Actions workflows. Several data files exist only to feed a Python
       script, a slash command, or a design doc, not a Hugo template, and
       are legitimately "read" that way.
    3. Mention by filename+extension (e.g. "arm_fetch_object.yaml") in
       that same set plus content/ — looser than #2 (no directory
       prefix required) but still requires the extension, which is
       specific enough to avoid #1's prose-collision problem.
    4. Directory access — a script or doc that references the file's
       containing data/ directory (e.g. "data/robots/organs/", including
       as a glob prefix like "data/robots/organs/*.yaml") is treated as
       reading every file under it, since scripts commonly walk a whole
       directory rather than naming each member file."""
    data_dir = ROOT / "data"
    template_haystack = ""
    for p in list((ROOT / "layouts").rglob("*.html")) + list(
        (ROOT / "content").rglob("*.md")
    ):
        template_haystack += p.read_text(encoding="utf-8", errors="ignore")

    repo_haystack = ""
    self_exclude = {Path(__file__).resolve(), (ROOT / "SITE-MAP.md").resolve()}
    for p in (
        list((ROOT / "scripts").rglob("*.py"))
        + list((ROOT / "docs").rglob("*.md"))
        + list((ROOT / "docs").rglob("*.yaml"))
        + list(ROOT.glob("*.md"))
        + list((ROOT / ".github" / "workflows").glob("*.yml"))
        + list((ROOT / ".claude" / "commands").glob("*.md"))
    ):
        if p.resolve() in self_exclude:
            # this script's own docstrings quote example paths, and
            # SITE-MAP.md is generated output — without this exclusion,
            # a file this function flags "unread" gets its path printed
            # into SITE-MAP.md, which the *next* run then reads back as
            # a reference and un-flags, oscillating run to run.
            continue
        repo_haystack += p.read_text(encoding="utf-8", errors="ignore")

    unread = []
    for p in data_dir.rglob("*.yaml"):
        rel = p.relative_to(data_dir)
        # a nested file is usually addressed by its parent dir name
        # (e.g. data/dinger_palooza/members.yaml -> Data.dinger_palooza)
        needle = rel.parts[0].replace(".yaml", "")
        candidates = {needle, p.stem}  # parent-dir namespace, or own leaf name
        read_by_template = any(
            re.search(r"Data\." + re.escape(c) + r"\b", template_haystack)
            for c in candidates
        )
        combined = template_haystack + repo_haystack
        read_by_path = str(rel).replace("\\", "/") in repo_haystack
        read_by_filename = p.name in combined
        dir_rel = str(rel.parent).replace("\\", "/")
        read_by_dir = dir_rel != "." and f"data/{dir_rel}/" in combined
        if not (read_by_template or read_by_path or read_by_filename or read_by_dir):
            unread.append(str(rel).replace("\\", "/"))
    return sorted(unread)


def load_hub_member_urls():
    """URLs that are members of a hub — reachable via the Connections
    strip + hub page even without a menu entry or homepage card, so the
    orphan check shouldn't flag them. Parses front matter directly
    rather than importing Hugo, since this is a one-off read at audit
    time, not a render."""
    import yaml

    urls = set()
    hubs_dir = ROOT / "content" / "hubs"
    if not hubs_dir.exists():
        return urls
    for p in hubs_dir.glob("*.md"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        if not text.startswith("---"):
            continue
        front_matter = text.split("---", 2)[1]
        data = yaml.safe_load(front_matter) or {}
        for member in data.get("members", []):
            urls.add(member["path"].strip("/"))
    return urls


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
    hub_member_urls = load_hub_member_urls()

    menu_urls = {m["url"] for m in menu}
    if cards is None:
        # No built public/ to check against — the homepage loop template
        # guarantees a card per menu leaf, so assume that held.
        cards = []
        card_urls = set(menu_urls)
        card_by_url = {}
    else:
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

        if (
            not in_menu
            and not has_card
            and url not in NON_MENU_SECTIONS
            and url not in hub_member_urls
        ):
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

    return rows, orphans, menu, card_urls, card_by_url


def render_markdown(rows, orphans, menu, card_urls, dead_layouts, unread_data):
    lines = []
    lines.append(START_MARKER)
    lines.append("")
    lines.append(
        f"_Generated by `scripts/site_audit.py`. "
        f"{len(menu)} menu items, {len(card_urls)} homepage cards, "
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
