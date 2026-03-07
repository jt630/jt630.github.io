Create a new Hugo post for the Almond Farm site.

Ask the user for:
1. **Section** — which tab does this belong to? Options with existing content: `blog`, `cooking`, `farming`. Others are valid too: `gaming`, `art`, `movies`, `drinks`, `body`, `gadgets`.
2. **Title** — what's the post called?
3. **Description** — one sentence for the frontmatter (used in cards and meta).

Then:
- Derive a URL-safe filename: lowercase the title, replace spaces with hyphens, strip punctuation. Example: "Mount Misery Trail" → `mount-misery-trail.md`
- Create the file at `content/{section}/{filename}.md`
- Use this exact frontmatter:

```
---
title: "{Title}"
date: {today's date as YYYY-MM-DD}
description: "{description}"
draft: false
---
```

- Add a single blank line after the frontmatter, then `<!-- write here -->` as a placeholder
- Confirm the file path to the user and open it for editing
