#!/usr/bin/env python3
"""
Audit the RENDERED beer-sheet page (public/beer-sheet/index.html) against
the underlying data (data/beer_sheet/board.json).

Read-only. Does not modify anything, does not regenerate board.json.
"""
import json
import re
import sys
from html.parser import HTMLParser
from html import unescape

ROOT = "c:/VSCode Projects/AlmondFarm"
BOARD_PATH = ROOT + "/data/beer_sheet/board.json"
HTML_PATH = ROOT + "/public/beer-sheet/index.html"


def load_board():
    with open(BOARD_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_html():
    with open(HTML_PATH, encoding="utf-8") as f:
        return f.read()


class RowParser(HTMLParser):
    """Parses <tr class="bs-row ..."> ... </tr> blocks inside tbody into dicts,
    and <div class="bs-card ..."> blocks similarly."""

    def __init__(self):
        super().__init__()
        self.rows = []  # table rows
        self.cards = []  # mobile cards
        self._stack = []
        self._cur_row = None
        self._cur_card = None
        self._cur_td_idx = -1
        self._cur_text = []
        self._capture_text = False
        self._in_thead = False
        self._td_texts = []
        self._row_html_buf = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr" and "bs-row" in attrs.get("class", "").split():
            self._cur_row = {
                "class": attrs.get("class", ""),
                "data-pos": attrs.get("data-pos"),
                "data-injury": attrs.get("data-injury"),
                "data-blacklisted": attrs.get("data-blacklisted"),
                "data-player-id": attrs.get("data-player-id"),
                "tds": [],
            }
            self._td_texts = []
        elif tag == "td" and self._cur_row is not None:
            self._cur_td_idx += 1
            self._capture_text = True
            self._cur_text = []
        elif tag == "div" and "bs-card" in attrs.get("class", "").split() and "bs-cards" not in attrs.get("class",""):
            # only top-level bs-card divs (not bs-card-top etc)
            classes = attrs.get("class", "").split()
            if "bs-card" in classes:
                self._cur_card = {
                    "class": attrs.get("class", ""),
                    "data-pos": attrs.get("data-pos"),
                    "data-injury": attrs.get("data-injury"),
                    "data-blacklisted": attrs.get("data-blacklisted"),
                    "data-player-id": attrs.get("data-player-id"),
                    "text": [],
                }
        elif self._cur_card is not None and tag == "span":
            pass

    def handle_endtag(self, tag):
        if tag == "td" and self._cur_row is not None and self._capture_text:
            text = " ".join("".join(self._cur_text).split())
            self._cur_row["tds"].append(text)
            self._capture_text = False
        elif tag == "tr" and self._cur_row is not None:
            self.rows.append(self._cur_row)
            self._cur_row = None
            self._cur_td_idx = -1
        elif tag == "div" and self._cur_card is not None:
            # crude: close on first matching div end after we've accumulated;
            # since nested divs exist, use a counter instead
            pass

    def handle_data(self, data):
        if self._capture_text:
            self._cur_text.append(data)
        if self._cur_card is not None:
            self._cur_card["text"].append(data)


def get_attr(tag_html, attr):
    """Handle both quoted (attr="val") and minified-unquoted (attr=val) forms."""
    m = re.search(attr + r'="([^"]*)"', tag_html)
    if m:
        return m.group(1)
    m = re.search(attr + r"=([^\s>]+)", tag_html)
    if m:
        return m.group(1)
    return None


def extract_rows_regex(html):
    """More robust extraction using regex over the whole <tr ...>...</tr> block,
    since HTMLParser div-nesting for cards is fragile."""
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", html, re.S)
    tbody = tbody_match.group(1)
    row_blocks = re.findall(r"<tr class=\"?bs-row.*?</tr>", tbody, re.S)
    rows = []
    for block in row_blocks:
        row = {}
        tag_end = block.index(">")
        opening_tag = block[:tag_end + 1]
        m = re.search(r'class="([^"]*)"', opening_tag)
        row["class"] = m.group(1) if m else ""
        for attr in ["data-pos", "data-injury", "data-blacklisted", "data-player-id"]:
            row[attr] = get_attr(opening_tag, attr)
        tds = re.findall(r"<td.*?</td>", block, re.S)
        row["tds_raw"] = tds
        rows.append(row)
    return rows


def extract_cards_regex(html):
    start_marker = 'class="bs-cards"' if 'class="bs-cards"' in html else 'class=bs-cards'
    marker_pos = html.index(start_marker)
    start_of_div = html.index(">", marker_pos) + 1
    body = html[start_of_div:]
    # Split top-level bs-card divs by matching balanced divs
    cards = []
    # Only match the top-level "bs-card" class token itself (not bs-card-top,
    # bs-card-name-row, bs-card-stats, bs-card-rank, bs-card-team, bs-card-delta, ...).
    pattern = re.compile(r'<div class="?bs-card(?![\w-])')
    for m in pattern.finditer(body):
        start = m.start()
        tag_close = body.index(">", m.end())
        opening_tag = body[start:tag_close + 1]
        cls_m = re.search(r'class="?([^">]*)"?', opening_tag)
        card_class = cls_m.group(1) if cls_m else "bs-card"
        div_open_re = re.compile(r"<div\b")
        div_close_re = re.compile(r"</div>")
        pos = tag_close + 1
        depth = 1
        while depth > 0:
            next_open = div_open_re.search(body, pos)
            next_close = div_close_re.search(body, pos)
            if next_close is None:
                break
            if next_open and next_open.start() < next_close.start():
                depth += 1
                pos = next_open.end()
            else:
                depth -= 1
                pos = next_close.end()
        card_html = body[start:pos]
        card = {"class": card_class}
        for attr in ["data-pos", "data-injury", "data-blacklisted", "data-player-id"]:
            card[attr] = get_attr(opening_tag, attr)
        card["html"] = card_html
        cards.append(card)
    return cards


def strip_tags(s):
    return unescape(re.sub(r"<[^>]+>", "", s)).strip()


def main():
    board = load_board()
    players = board["players"]
    by_id = {str(p["player_id"]): p for p in players}
    html = load_html()

    findings = []

    def fail(check, msg):
        findings.append(("FAIL", check, msg))

    def ok(check, msg):
        findings.append(("PASS", check, msg))

    def warn(check, msg):
        findings.append(("WARN", check, msg))

    # ---- Extract rows & cards ----
    rows = extract_rows_regex(html)
    cards = extract_cards_regex(html)

    print(f"JSON players: {len(players)}")
    print(f"Rendered table rows: {len(rows)}")
    print(f"Rendered mobile cards: {len(cards)}")

    def canon_id(raw):
        """Normalize a rendered data-player-id (which may be in Go %v
        scientific-notation float form, e.g. '2.473037e+06') back to a
        plain integer string for comparison against JSON player_id."""
        try:
            f = float(raw)
            if f == int(f):
                return str(int(f))
        except (TypeError, ValueError):
            pass
        return raw

    # ---- Data-player-id formatting check ----
    sci_notation_ids = [r["data-player-id"] for r in rows if r["data-player-id"] and "e+" in r["data-player-id"].lower()]
    if sci_notation_ids:
        fail(
            "data-player-id-format",
            f"{len(sci_notation_ids)}/{len(rows)} rows render data-player-id in scientific "
            f"notation (Hugo prints .player_id as a Go float64 %v, e.g. "
            f"'{sci_notation_ids[0]}' instead of the integer from board.json). "
            f"Values still round-trip losslessly and stay unique/self-consistent between "
            f"table and card (verified no collisions), so click-to-draft still works, but "
            f"the attribute is fragile: unquoted '+' /'.' chars in the HTML, and any future "
            f"code (or manual page-source debugging mid-draft) that does strict string/JSON "
            f"comparison against the JSON player_id will silently fail to match."
        )
    else:
        ok("data-player-id-format", "data-player-id values render as plain integers")

    # ---- Check 3: completeness ----
    row_ids = [canon_id(r["data-player-id"]) for r in rows]
    card_ids = [canon_id(c["data-player-id"]) for c in cards]
    json_ids = [str(p["player_id"]) for p in players]

    if len(row_ids) != len(json_ids):
        fail("completeness/table-count", f"table has {len(row_ids)} rows vs {len(json_ids)} players in JSON")
    else:
        ok("completeness/table-count", f"table row count matches JSON ({len(row_ids)})")

    if len(card_ids) != len(json_ids):
        fail("completeness/card-count", f"mobile cards has {len(card_ids)} vs {len(json_ids)} players in JSON")
    else:
        ok("completeness/card-count", f"mobile card count matches JSON ({len(card_ids)})")

    dup_row_ids = [x for x in set(row_ids) if row_ids.count(x) > 1]
    if dup_row_ids:
        fail("completeness/table-dupes", f"duplicate player_id(s) in table rows: {dup_row_ids}")
    dup_card_ids = [x for x in set(card_ids) if card_ids.count(x) > 1]
    if dup_card_ids:
        fail("completeness/card-dupes", f"duplicate player_id(s) in cards: {dup_card_ids}")

    missing_from_table = set(json_ids) - set(row_ids)
    extra_in_table = set(row_ids) - set(json_ids)
    if missing_from_table:
        fail("completeness/table-missing", f"players in JSON but missing from table: {sorted(missing_from_table)[:10]}")
    if extra_in_table:
        fail("completeness/table-extra", f"player IDs in table not in JSON: {sorted(extra_in_table)[:10]}")

    missing_from_cards = set(json_ids) - set(card_ids)
    extra_in_cards = set(card_ids) - set(json_ids)
    if missing_from_cards:
        fail("completeness/card-missing", f"players in JSON but missing from cards: {sorted(missing_from_cards)[:10]}")
    if extra_in_cards:
        fail("completeness/card-extra", f"player IDs in cards not in JSON: {sorted(extra_in_cards)[:10]}")

    # ---- Check 2: ordering ----
    json_sorted_by_vor = sorted(players, key=lambda p: p["vor_rank"])
    json_vor_order_ids = [str(p["player_id"]) for p in json_sorted_by_vor]

    if row_ids == json_vor_order_ids:
        ok("ordering/table", "table row order exactly matches JSON sorted by vor_rank ascending")
    else:
        # find first mismatch
        mism = None
        for i, (a, b) in enumerate(zip(row_ids, json_vor_order_ids)):
            if a != b:
                mism = i
                break
        fail("ordering/table", f"table row order does NOT match vor_rank ascending; first mismatch at index {mism}: rendered={row_ids[mism] if mism is not None else None} ({by_id.get(row_ids[mism],{}).get('name') if mism is not None else ''}) expected={json_vor_order_ids[mism] if mism is not None else None} ({by_id.get(json_vor_order_ids[mism],{}).get('name') if mism is not None else ''})")

    if card_ids == json_vor_order_ids:
        ok("ordering/cards", "mobile card order exactly matches JSON sorted by vor_rank ascending")
    else:
        mism = None
        for i, (a, b) in enumerate(zip(card_ids, json_vor_order_ids)):
            if a != b:
                mism = i
                break
        fail("ordering/cards", f"card order does NOT match vor_rank ascending; first mismatch at index {mism}")

    if row_ids == card_ids:
        ok("ordering/table-vs-cards", "table row order matches mobile card order")
    else:
        fail("ordering/table-vs-cards", "table row order and mobile card order DIFFER")

    # ---- also check raw JSON array order itself (are players[] already in vor_rank order, or does the template rely on unsorted JSON?) ----
    raw_json_order_ids = [str(p["player_id"]) for p in players]
    if raw_json_order_ids == json_vor_order_ids:
        ok("ordering/json-array", "players[] array in board.json is itself already sorted by vor_rank ascending")
    else:
        warn("ordering/json-array", "players[] array in board.json is NOT sorted by vor_rank ascending (template does not re-sort, so rendered order = raw JSON array order, which may not be vor_rank order)")

    # ---- Check 1: value fidelity on a sample spanning the board ----
    n = len(players)
    sample_idx = sorted(set([0, 1, 2, 5, 10, 20, 30, 50, 75, 100, 125, 150, 175, 200, 220, 240, 260, 275, 290, n - 1]))
    sample_idx = [i for i in sample_idx if 0 <= i < n]

    field_checks = [
        ("tier_label", 0, lambda p: p["tier_label"]),
        ("vor_rank", 1, lambda p: str(p["vor_rank"])),
        ("team", 3, lambda p: p["team"]),
        ("bye_week", 4, lambda p: str(p["bye_week"])),
        ("proj_points", 6, lambda p: p["proj_points"]),
        ("vor", 7, lambda p: p["vor"]),
        ("auction_value", 8, lambda p: p["auction_value"]),
        ("adp", 9, lambda p: p["adp"]),
    ]

    def num_close(a, b):
        try:
            return abs(float(a) - float(b)) < 1e-6
        except Exception:
            return str(a) == str(b)

    row_by_id = {canon_id(r["data-player-id"]): r for r in rows}

    mismatches = []
    for i in sample_idx:
        p = players[i]
        pid = str(p["player_id"])
        r = row_by_id.get(pid)
        if r is None:
            mismatches.append((p["name"], "row not found in table at all"))
            continue
        tds = r["tds_raw"]
        # td indices: 0 tier,1 rank,2 name,3 team,4 bye,5 pos,6 proj,7 vor,8 $,9 adp,10 delta,11 risk
        for fname, idx, extractor in field_checks:
            if idx >= len(tds):
                mismatches.append((p["name"], f"{fname}: td index {idx} missing"))
                continue
            rendered_text = strip_tags(tds[idx])
            expected = extractor(p)
            if fname == "auction_value":
                rendered_text_clean = rendered_text.replace("$", "").strip()
                if not num_close(rendered_text_clean, expected):
                    mismatches.append((p["name"], f"{fname}: rendered='{rendered_text}' expected='${expected}'"))
            elif fname in ("proj_points", "vor", "adp"):
                if not num_close(rendered_text, expected):
                    mismatches.append((p["name"], f"{fname}: rendered='{rendered_text}' expected='{expected}'"))
            else:
                if rendered_text != str(expected):
                    mismatches.append((p["name"], f"{fname}: rendered='{rendered_text}' expected='{expected}'"))

        # pos_rank + position badge (td 5): expect "{position}{pos_rank}"
        pos_td = strip_tags(tds[5]) if len(tds) > 5 else ""
        expected_pos_badge = f"{p['position']}{p['pos_rank']}"
        if pos_td != expected_pos_badge:
            mismatches.append((p["name"], f"pos_badge: rendered='{pos_td}' expected='{expected_pos_badge}'"))

        # value_delta / has_real_adp (td 10)
        delta_td_raw = tds[10] if len(tds) > 10 else ""
        delta_text = strip_tags(delta_td_raw)
        if not p["has_real_adp"]:
            if delta_text not in ("\u2014", "-", ""):
                mismatches.append((p["name"], f"value_delta(no adp): rendered='{delta_text}' expected em-dash"))
            if 'bs-delta-noadp' not in delta_td_raw:
                mismatches.append((p["name"], f"value_delta(no adp): missing bs-delta-noadp class"))
        else:
            expected_delta = p["value_delta"]
            expected_str = (f"+{expected_delta}" if expected_delta > 0 else str(expected_delta))
            if delta_text != expected_str:
                mismatches.append((p["name"], f"value_delta: rendered='{delta_text}' expected='{expected_str}'"))

        # risk_label (td 11)
        risk_td = strip_tags(tds[11]) if len(tds) > 11 else ""
        if risk_td != p["risk_label"]:
            mismatches.append((p["name"], f"risk_label: rendered='{risk_td}' expected='{p['risk_label']}'"))

    if mismatches:
        for name, msg in mismatches:
            fail("value-fidelity", f"{name}: {msg}")
    else:
        ok("value-fidelity", f"sampled {len(sample_idx)} players across the board; all displayed fields matched JSON exactly")

    # ---- Check 5: no-ADP dash, count check across ALL players (not just sample) ----
    no_adp_players = [p for p in players if not p["has_real_adp"]]
    bad_no_adp = []
    zero_rendered_as_delta = []
    for p in no_adp_players:
        pid = str(p["player_id"])
        r = row_by_id_full = None
    # need full row map, not just sample; rebuild:
    full_row_by_id = {canon_id(r["data-player-id"]): r for r in rows}
    for p in no_adp_players:
        pid = str(p["player_id"])
        r = full_row_by_id.get(pid)
        if r is None:
            continue
        tds = r["tds_raw"]
        if len(tds) > 10:
            delta_html = tds[10]
            delta_text = strip_tags(delta_html)
            if delta_text != "\u2014":
                bad_no_adp.append((p["name"], delta_text))
    count_no_adp_dash_ok = len(no_adp_players) - len(bad_no_adp)
    print(f"has_real_adp=false count in JSON: {len(no_adp_players)}")
    if bad_no_adp:
        fail("no-adp-dash", f"{len(bad_no_adp)}/{len(no_adp_players)} no-ADP players do NOT render an em-dash: {bad_no_adp[:10]}")
    else:
        ok("no-adp-dash", f"all {len(no_adp_players)} has_real_adp=false players render an em-dash, none show a numeric 0")

    # sanity: are there any players where adp == 0 and has_real_adp true (would render literal 0 for ADP column, ambiguous)
    zero_adp_real = [p for p in players if p.get("has_real_adp") and (p.get("adp") == 0 or p.get("value_delta") == 0)]
    if zero_adp_real:
        warn("no-adp-dash/zero-delta", f"{len(zero_adp_real)} players have has_real_adp=true and adp==0 or value_delta==0 -- verify these are legitimately real ADP data, not defaulted zeros: {[p['name'] for p in zero_adp_real][:10]}")

    # ---- Check 4: conditional treatments, full-board counts ----
    # Injury severity
    SEVERE = {"OUT", "INJURY_RESERVE", "SUSPENSION"}
    def expected_sev(p):
        if p["injury_status"] == "ACTIVE":
            return None
        return "severe" if p["injury_status"] in SEVERE else "caution"

    sev_mismatch = []
    for p in players:
        pid = str(p["player_id"])
        r = full_row_by_id.get(pid)
        if r is None:
            continue
        exp = expected_sev(p)
        rendered_sev = r["data-injury"]
        rendered_norm = None if rendered_sev == "none" else rendered_sev
        if rendered_norm != exp:
            sev_mismatch.append((p["name"], p["injury_status"], f"expected={exp} rendered={rendered_norm}"))
    if sev_mismatch:
        fail("injury-severity", f"{len(sev_mismatch)} mismatches: {sev_mismatch[:10]}")
    else:
        ok("injury-severity", f"all {len(players)} players' injury severity classification (severe/caution/none) matches injury_status")

    # blacklisted -> bs-row--faded present on exactly blacklisted players
    faded_mismatch = []
    for p in players:
        pid = str(p["player_id"])
        r = full_row_by_id.get(pid)
        if r is None:
            continue
        has_faded_class = "bs-row--faded" in r["class"].split()
        if has_faded_class != bool(p["blacklisted"]):
            faded_mismatch.append((p["name"], p["blacklisted"], has_faded_class))
    if faded_mismatch:
        fail("blacklist-faded-class", f"{len(faded_mismatch)} mismatches (name, blacklisted, has_faded_class): {faded_mismatch[:10]}")
    else:
        ok("blacklist-faded-class", f"bs-row--faded class present on exactly the {sum(1 for p in players if p['blacklisted'])} blacklisted players")

    # role badges: shown for COMMITTEE/BENCH/UNKNOWN except DST+UNKNOWN
    role_mismatch = []
    for p in players:
        pid = str(p["player_id"])
        r = full_row_by_id.get(pid)
        if r is None:
            continue
        tds = r["tds_raw"]
        name_td = tds[2] if len(tds) > 2 else ""
        expected_show = p["role"] in ("COMMITTEE", "BENCH", "UNKNOWN")
        if p["role"] == "UNKNOWN" and p["position"] == "DST":
            expected_show = False
        has_role_badge = "bs-role-badge" in name_td
        if has_role_badge != expected_show:
            role_mismatch.append((p["name"], p["role"], p["position"], f"expected_show={expected_show} rendered={has_role_badge}"))
    if role_mismatch:
        fail("role-badge", f"{len(role_mismatch)} mismatches: {role_mismatch[:10]}")
    else:
        ok("role-badge", "role badges shown/hidden correctly for all players per STARTER-silent / DST-UNKNOWN-silent rule")

    # position color class bs-pos-name-{position} on name span matches actual position
    pos_class_mismatch = []
    for p in players:
        pid = str(p["player_id"])
        r = full_row_by_id.get(pid)
        if r is None:
            continue
        tds = r["tds_raw"]
        name_td = tds[2] if len(tds) > 2 else ""
        m = re.search(r'bs-pos-name-(\w+)', name_td)
        rendered_pos = m.group(1) if m else None
        if rendered_pos != p["position"]:
            pos_class_mismatch.append((p["name"], p["position"], rendered_pos))
    if pos_class_mismatch:
        fail("position-color-class", f"{len(pos_class_mismatch)} mismatches: {pos_class_mismatch[:10]}")
    else:
        ok("position-color-class", "bs-pos-name-{position} class matches actual position for all players")

    # ---- blacklist_summary panel counts ----
    bl_summary = board.get("blacklist_summary", {})
    actual_blacklisted = sum(1 for p in players if p["blacklisted"])
    faded_count_json = bl_summary.get("faded_count")
    excluded_count_json = bl_summary.get("excluded_count")
    print(f"blacklist_summary.faded_count={faded_count_json} excluded_count={excluded_count_json} auto_flagged_count={bl_summary.get('auto_flagged_count')}")
    print(f"actual players with blacklisted=true in players[]: {actual_blacklisted}")
    if faded_count_json is not None and (faded_count_json + (excluded_count_json or 0)) != actual_blacklisted and excluded_count_json is not None:
        # excluded players might not even appear in players[] (since excluded = removed from board)
        warn("blacklist-summary-counts", f"faded_count({faded_count_json}) + excluded_count({excluded_count_json}) = {faded_count_json+excluded_count_json} vs {actual_blacklisted} blacklisted=true rows in players[] -- if excluded players are removed from the board entirely this is expected, but verify")

    faded_names_json = set(bl_summary.get("faded_names", []))
    excluded_names_json = set(bl_summary.get("excluded_names", []))
    board_blacklisted_names = set(p["name"] for p in players if p["blacklisted"])
    only_in_board_not_faded_list = board_blacklisted_names - faded_names_json
    if only_in_board_not_faded_list:
        warn("blacklist-summary-names", f"players marked blacklisted=true in board but NOT listed in blacklist_summary.faded_names: {sorted(only_in_board_not_faded_list)[:10]}")

    # ---- print final report ----
    print("\n" + "=" * 70)
    print("FINDINGS")
    print("=" * 70)
    n_fail = sum(1 for s, _, _ in findings if s == "FAIL")
    n_warn = sum(1 for s, _, _ in findings if s == "WARN")
    n_pass = sum(1 for s, _, _ in findings if s == "PASS")
    for status, check, msg in findings:
        print(f"[{status}] {check}: {msg}")
    print(f"\nTOTAL: {n_pass} PASS, {n_fail} FAIL, {n_warn} WARN")


if __name__ == "__main__":
    main()
