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

All content lives in the `content/` folder as Markdown files. Each file starts with **front matter** (the stuff between `---` lines) followed by your content.

### Blog Post

Create a new file at `content/blog/your-post-title.md`:

```markdown
---
title: "Your Post Title"
date: 2024-08-10
author: "Your Name"
description: "A short summary that shows up in previews."
---

Write your post here in regular Markdown.

Use **bold**, *italics*, [links](https://example.com), etc.

> Blockquotes look like this.

You can add images if you put them in `static/images/` first:

![alt text](/images/my-photo.jpg)
```

Or use the Hugo command to scaffold it:

```bash
hugo new blog/your-post-title.md
```

### Recipe

Create a new file at `content/cooking/recipe-name.md`:

```markdown
---
title: "Recipe Name"
date: 2024-08-10
author: "Your Name"
description: "Short description of the dish."
---

**What it is** — Brief intro to the dish.

## Ingredients

- 2 lbs potatoes
- 1 lb sausage
- 1 onion, diced
- Salt, pepper, garlic

## Steps

1. Prep your vegetables.
2. Heat oil in a pan over medium heat.
3. Cook the potatoes until golden.
4. Add sausage and onions, cook until done.
5. Season and serve.

## Notes

Any tips, variations, or stories about the dish.
```

Or scaffold it:

```bash
hugo new cooking/recipe-name.md
```

### Farm Update

Create a new file at `content/farming/update-name.md`:

```markdown
---
title: "Update Title"
date: 2024-08-10
author: "Your Name"
description: "What's happening on the farm."
---

Your farm update here. Add photos, talk about the harvest, weather, whatever.
```

Or scaffold it:

```bash
hugo new farming/update-name.md
```

### Music

Music is a single page. Edit `content/music.md` directly:

```markdown
---
title: "Music"
type: "page"
layout: "single"
description: "What we're listening to"
---

## Now Playing

**Album Name** by Artist — Short review. This album rips.

## Albums We're Into

- **Album 1** by Artist — One sentence review
- **Album 2** by Artist — One sentence review

## Playlists

- [Playlist Name](https://open.spotify.com/playlist/xxx) — Description
```

### Books

Same idea — edit `content/books.md` directly:

```markdown
---
title: "Books"
type: "page"
layout: "single"
description: "Our reading list"
---

## Currently Reading

**Book Title** by Author — Thoughts so far.

## Recommendations

- **Book 1** by Author — Why it's good
- **Book 2** by Author — Why it's good

## Finished

- **Book 3** by Author — Short review
```

### Gallery

Add images to `static/images/gallery/`, then reference them in `content/gallery.md`.

---

## Adding a Contributor

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

If you include a `photo`, put the image file in `static/images/`. If you skip `photo`, the site shows the person's first initial in a yellow circle.

---

## Project Structure

```
content/           ← All your content (Markdown files)
  blog/            ← Blog posts
  cooking/         ← Recipes
  farming/         ← Farm updates
  music.md         ← Music page (single file)
  books.md         ← Books page (single file)
  about.md         ← About page
  gallery.md       ← Gallery page
data/
  contributors.yaml  ← Contributor bios for the About page
static/
  images/          ← Put your images here
  CNAME            ← Custom domain config
assets/css/
  main.css         ← All the site styling
layouts/           ← Hugo templates (you probably don't need to touch these)
archetypes/        ← Templates for `hugo new` commands
hugo.toml          ← Site config (title, menu, settings)
.github/workflows/ ← Auto-deploy on push to main
```

---

## Markdown Cheat Sheet

```markdown
**bold text**
*italic text*
[link text](https://url.com)
![image alt](/images/filename.jpg)

> blockquote

- bullet list
- another item

1. numbered list
2. another item

## Heading 2
### Heading 3

---  (horizontal rule)
```

---

## Deployment

Push to `main` and GitHub Actions builds + deploys automatically. That's it.
