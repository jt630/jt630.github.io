Scan a grocery receipt photo and log the purchase to data/shopping_log.yaml.

## Steps

1. Ask the user: "Drop the path to your receipt photo (or drag it in)."

2. Read the image file at the provided path using the Read tool.

3. Extract from the receipt:
   - `store` — store name (e.g. Costco, Trader Joe's, Kroger)
   - `date` — purchase date in YYYY-MM-DD format (use today if not visible)
   - `items` — each line item with:
     - `name` — clean product name (drop store brand prefixes, SKU noise)
     - `qty` — quantity + unit if visible (e.g. "3 lbs", "2 ct", "1 gal")
     - `price` — price as float
     - `category` — infer from item: produce | protein | dairy | pantry | frozen | beverage | household | other
   - `total` — receipt total if visible
   - `notes` — anything worth flagging (sale items, bulk buys, etc.)

4. Read data/shopping_log.yaml to see existing entries.

5. Append the new entry to the top of the log (most recent first). Format:

```yaml
- date: YYYY-MM-DD
  store: Store Name
  items:
    - name: chicken thighs
      qty: "3 lbs"
      price: 8.99
      category: protein
    - name: soy sauce
      qty: "1 bottle"
      price: 4.49
      category: pantry
  total: 87.45
  notes: ""
```

6. Write the updated file back.

7. After saving, print a quick summary:
   - How many items logged
   - Any items that appear in data/recipes/staples.yaml key_ingredients (flag these — they feed the meal planner)
   - Any items that look like pantry staples (offer to update data/pantry_inventory.yaml too)

8. Ask: "Want me to check what meals from your staples list you could make with what you just bought?"
