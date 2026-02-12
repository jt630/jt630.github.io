# Almond Farm

A lifestyle website built with [Hugo](https://gohugo.io/) and hosted on GitHub Pages at **almondfarm.us**.

## Quick Start

### Prerequisites

Install Hugo (extended version): https://gohugo.io/installation/

### Run locally

```bash
hugo server
```

Open http://localhost:1313 to preview. The site auto-reloads when you save changes.

### Build for production

```bash
hugo --minify
```

Output goes to `public/`. Deployment is handled automatically by GitHub Actions on push to `main`.

---

## Adding Content

### Blog Post

Create `content/blog/your-post-title.md`:

```markdown
---
title: "Your Post Title"
date: 2024-08-10
author: "JT"
description: "A short summary that shows up in previews."
---

Write your post here in Markdown.
```

Or scaffold: `hugo new blog/your-post-title.md`

### Recipe

Create `content/cooking/recipe-name.md`:

```markdown
---
title: "Recipe Name"
date: 2024-08-10
author: "JT"
description: "Short description of the dish."
---

**What it is** — Brief intro to the dish.

## Ingredients

- 2 lbs potatoes
- 1 lb sausage

## Steps

1. Prep your vegetables.
2. Cook them.

## Notes

Any tips or variations.
```

Or scaffold: `hugo new cooking/recipe-name.md`

### Farm Update

Create `content/farming/update-name.md`:

```markdown
---
title: "Update Title"
date: 2024-08-10
author: "JT"
description: "What's happening on the farm."
---

Your farm update here.
```

Or scaffold: `hugo new farming/update-name.md`

### Music

Music is data-driven. Edit `data/music.yaml`:

```yaml
albums:
  - title: "Blonde"
    artist: "Frank Ocean"
    year: 2016
    note: "Still hits."
    link: "https://open.spotify.com/album/..."

playlists:
  - name: "Fire Camp"
    description: "What we play on the 14-day rolls."
    link: "https://open.spotify.com/playlist/..."
```

Add entries and they render as cards on the Music page automatically.

### Books

Edit `data/books.yaml`. Each book needs a `status` of `reading`, `finished`, or `recommended`:

```yaml
books:
  - title: "Blood Meridian"
    author: "Cormac McCarthy"
    status: "finished"
    note: "Brutal and beautiful."

  - title: "Braiding Sweetgrass"
    author: "Robin Wall Kimmerer"
    status: "reading"
```

The Books page automatically groups them into Currently Reading, Finished, and Recommendations.

### Gallery

Drop images (`.jpg`, `.png`, `.webp`, `.gif`) into `static/images/gallery/` and they show up on the Gallery page automatically. No markdown editing needed.

### Adding a Contributor

Edit `data/contributors.yaml`:

```yaml
- name: "JT"
  role: "Founder"
  bio: "Firefighter, farmer, cook. Born and raised."

- name: "Jake"
  role: "Contributor"
  bio: "Card shark. Pulaski carrier."
  photo: "/images/jake.jpg"
```

If you include a `photo`, put the image in `static/images/`. Without a photo, the site shows the person's first initial in a yellow circle.

---

## Project Structure

```
content/           ← Markdown content
  blog/            ← Blog posts
  cooking/         ← Recipes
  farming/         ← Farm updates
  music.md         ← Music page (renders from data/music.yaml)
  books.md         ← Books page (renders from data/books.yaml)
  gallery.md       ← Gallery page (scans static/images/gallery/)
  about.md         ← About page (renders from data/contributors.yaml)
data/
  music.yaml       ← Albums and playlists
  books.yaml       ← Reading list
  contributors.yaml ← Crew bios for the About page
static/
  images/          ← Images (gallery/ subfolder for Gallery page)
  CNAME            ← Custom domain config
assets/css/
  main.css         ← Site styling
layouts/           ← Hugo templates
archetypes/        ← Templates for `hugo new` commands
hugo.toml          ← Site config (title, menu, settings)
.github/workflows/ ← Auto-deploy on push to main
```

---

## Deployment

Push to `main` and GitHub Actions builds + deploys automatically.

**Important:** In your repo settings (Settings > Pages), make sure the Source is set to **GitHub Actions**, not "Deploy from a branch".
