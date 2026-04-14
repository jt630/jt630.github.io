Scan one or more photos of the fridge or pantry and update data/pantry_inventory.yaml.

This is a manual/one-time snapshot — not ongoing logging. Use it to refresh the pantry
inventory so the meal planner knows what you already have without needing to shop.

## Steps

1. Ask: "How many photos? Drop the path(s) — fridge, pantry shelf, freezer, whatever you have."
   Accept multiple paths, one at a time or as a list.

2. Read each image using the Read tool.

3. For each image, identify visible items:
   - Product name (clean, generic — "olive oil" not "Kirkland Signature Extra Virgin Olive Oil 2L")
   - Rough status: `full` | `half` | `low` | `trace` (almost gone)
   - Category: produce | protein | dairy | pantry | frozen | condiment | beverage | spice
   - Location hint if useful: fridge | freezer | pantry | counter

4. Read data/pantry_inventory.yaml (existing inventory).

5. Merge new observations with existing entries:
   - Update status for items already in the inventory
   - Add newly spotted items
   - Do NOT remove items just because they weren't visible — only update what you can see

6. Write the updated file. Format:

```yaml
last_updated: YYYY-MM-DD
items:
  - name: olive oil
    category: pantry
    status: half
    location: pantry
  - name: chicken thighs
    category: protein
    status: full
    location: freezer
    notes: "looks like ~3 lbs"
  - name: soy sauce
    category: condiment
    status: low
    location: pantry
```

7. After saving, print a summary grouped by status:
   - **Low / Trace** — things to add to the next shopping list
   - **Proteins on hand** — what meals from staples.yaml you could make right now
   - **Produce** — what needs to be used soon

8. Cross-reference with data/recipes/staples.yaml: list any staple meals that are fully
   makeable from what's on hand (all key_ingredients present at half or better).

9. Ask: "Want me to plan a week of meals using what's already in the pantry?"
