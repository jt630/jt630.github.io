#!/usr/bin/env python3
"""Fetch Open Library cover URLs for books in data/books.yaml.

If books.yaml does not exist, explain the current books data structure
and exit without error.
"""

import sys
import os
import urllib.request
import urllib.parse
import json
import yaml

BOOKS_YAML = os.path.join(os.path.dirname(__file__), "..", "data", "books.yaml")
COVER_BASE = "https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
OL_SEARCH = "https://openlibrary.org/search.json?title={title}&author={author}&limit=1"


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    books_path = os.path.normpath(BOOKS_YAML)

    if not os.path.exists(books_path):
        print(
            "data/books.yaml does not exist.\n"
            "\n"
            "The current books data lives in content/books.md as plain markdown.\n"
            "It has no structured book entries — just section headings and placeholder text.\n"
            "\n"
            "To use this script:\n"
            "  1. Create data/books.yaml with entries like:\n"
            "       - title: 'The Great Gatsby'\n"
            "         author: 'F. Scott Fitzgerald'\n"
            "  2. Re-run this script to add cover_url to each entry.\n"
        )
        sys.exit(0)

    with open(books_path, "r", encoding="utf-8") as f:
        books = yaml.safe_load(f) or []

    if not isinstance(books, list):
        print("ERROR: data/books.yaml is not a list of book entries.", file=sys.stderr)
        sys.exit(1)

    updated = 0
    for book in books:
        if book.get("cover_url"):
            print(f"  Skipping '{book.get('title')}' — cover_url already set.")
            continue

        title = urllib.parse.quote(str(book.get("title", "")))
        author = urllib.parse.quote(str(book.get("author", "")))
        url = OL_SEARCH.format(title=title, author=author)

        print(f"  Looking up: {book.get('title')} by {book.get('author')}...")
        try:
            data = fetch_json(url)
            docs = data.get("docs", [])
            if docs and docs[0].get("cover_i"):
                cover_id = docs[0]["cover_i"]
                book["cover_url"] = COVER_BASE.format(cover_id=cover_id)
                print(f"    Found cover id={cover_id}")
                updated += 1
            else:
                print(f"    No cover found.")
        except Exception as e:
            print(f"    Error fetching cover: {e}")

    with open(books_path, "w", encoding="utf-8") as f:
        yaml.dump(books, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"\nUpdated {updated} book entries with cover URLs in {books_path}")


if __name__ == "__main__":
    main()
