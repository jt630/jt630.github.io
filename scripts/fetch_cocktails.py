#!/usr/bin/env python3
"""Fetch 15 cocktails from TheCocktailDB and write to data/cocktails.yaml."""

import sys
import os
import urllib.request
import json
import yaml

BASE_URL = "https://www.thecocktaildb.com/api/json/v1/1"
DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "cocktails.yaml")


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    print("Fetching cocktail list...")
    data = fetch_json(f"{BASE_URL}/filter.php?c=Cocktail")
    drinks_list = data.get("drinks", [])
    if not drinks_list:
        print("ERROR: No drinks returned from filter endpoint.", file=sys.stderr)
        sys.exit(1)

    target = drinks_list[:15]
    cocktails = []

    for item in target:
        drink_id = item["idDrink"]
        print(f"  Fetching details for id={drink_id} ({item['strDrink']})...")
        detail_data = fetch_json(f"{BASE_URL}/lookup.php?i={drink_id}")
        drink = detail_data["drinks"][0]

        # Collect non-empty ingredients
        ingredients = []
        for i in range(1, 16):
            ing = drink.get(f"strIngredient{i}")
            if ing and ing.strip():
                ingredients.append(ing.strip())

        cocktails.append({
            "name": drink.get("strDrink", ""),
            "glass": drink.get("strGlass", ""),
            "category": drink.get("strCategory", ""),
            "instructions": drink.get("strInstructions", ""),
            "ingredients": ingredients,
            "thumb_url": drink.get("strDrinkThumb", ""),
        })

    out_path = os.path.normpath(DATA_FILE)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(cocktails, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"\nWrote {len(cocktails)} cocktails to {out_path}")


if __name__ == "__main__":
    main()
