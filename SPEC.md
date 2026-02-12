# Almond Farm — Website Spec Sheet

## Overview

**Almond Farm** (almondfarm.us) is a personal lifestyle website shared among a small group of friends/contributors. It covers blog posts, cooking, music, books, and farming. The site is bold, playful, and image-heavy.

---

## Branding

- **Name**: Almond Farm
- **Domain**: almondfarm.us (existing, via GitHub Pages CNAME)
- **Tone**: Casual, fun, personal — written for friends, not the public
- **Aesthetic**: Bold & playful — bright colors, fun animations, expressive personality

---

## Tech Stack

| Layer          | Choice                          | Notes                                      |
|----------------|---------------------------------|--------------------------------------------|
| **SSG**        | Hugo                            | Fast builds, Markdown content, Go-based    |
| **Hosting**    | GitHub Pages                    | Free, auto-deploys from repo               |
| **Styling**    | CSS (custom)                    | No framework — hand-crafted to match vibe  |
| **Images**     | Hugo asset pipeline             | Responsive image processing built-in       |
| **CMS**        | Deferred (future enhancement)   | Decap CMS is the leading candidate         |
| **CI/CD**      | GitHub Actions                  | Build Hugo site and deploy to GitHub Pages |
| **Domain**     | almondfarm.us via CNAME         | Already configured                         |

---

## Site Map

```
/                        → Homepage (landing + navigation hub)
/about/                  → About page with contributor bios
/blog/                   → Blog feed (dated posts)
/blog/:slug/             → Individual blog post
/cooking/                → Cooking feed (dated recipe posts)
/cooking/:slug/          → Individual recipe
/music/                  → Music page (curated list / reviews)
/books/                  → Books page (curated list / reviews)
/farming/                → Farming feed (dated updates)
/farming/:slug/          → Individual farming post
/gallery/                → Photo gallery page
```

---

## Content Sections

### 1. Blog (`/blog/`)
- **Type**: Feed of dated posts
- **Content model**: Title, date, author, tags, featured image, body (Markdown)
- **Display**: Reverse-chronological list with thumbnails
- **Existing content**: Firefighter Chronicles posts (migrate from current Blog.html)

### 2. Cooking (`/cooking/`)
- **Type**: Feed of dated recipe posts
- **Content model**: Title, date, author, featured image, ingredients list, instructions, body (Markdown)
- **Display**: Card grid with food photos
- **Existing content**: Salchichas Papa recipe (migrate from current Cooking.html)

### 3. Music (`/music/`)
- **Type**: Curated single page (not a feed)
- **Content model**: Single Markdown page with sections for albums, playlists, recommendations
- **Display**: Styled page with album art, embedded links (Spotify/YouTube), short reviews

### 4. Books (`/books/`)
- **Type**: Curated single page (not a feed)
- **Content model**: Single Markdown page with book entries (title, author, cover image, short review/rating)
- **Display**: Styled list or grid of book cards

### 5. Farming (`/farming/`)
- **Type**: Feed of dated posts
- **Content model**: Title, date, author, featured image, body (Markdown)
- **Display**: Reverse-chronological list, image-heavy (farm photos)

---

## Standalone Pages

### Homepage (`/`)
- Hero section with "Almond Farm" branding
- Animated/fun navigation cards linking to each section
- Recent posts preview (latest from blog, cooking, farming)

### About (`/about/`)
- Site description / mission
- Contributor bios: name, photo, short bio, role/interests
- Stored as data file (Hugo `data/contributors.yaml` or similar)

### Photo Gallery (`/gallery/`)
- Grid of images pulled from across the site or a dedicated gallery folder
- Lightbox-style viewing (CSS-only or minimal JS)

---

## Design Direction

### Bold & Playful
- **Colors**: Bright, saturated palette — think warm yellows, vibrant greens, punchy oranges, with a dark accent
- **Typography**: A fun display font for headings, clean sans-serif for body text (Google Fonts, free)
- **Animations**: Hover effects on cards (scale, color shifts), smooth page transitions
- **Shape language**: Rounded corners, playful borders, maybe subtle blob/organic shapes
- **Images**: Large, prominent — hero images, thumbnails on every post, photo-forward layout
- **Spacing**: Generous — breathable layout, not cramped

### Responsive
- Mobile-first design
- Hamburger nav on mobile, horizontal nav on desktop
- Images scale and reflow gracefully

---

## Hugo Structure

```
jt630.github.io/
├── archetypes/              # Content templates (blog post, recipe, etc.)
│   ├── blog.md
│   ├── cooking.md
│   └── farming.md
├── assets/
│   └── css/
│       └── main.css         # Site-wide styles
├── content/
│   ├── blog/                # Blog posts (Markdown files)
│   ├── cooking/             # Recipe posts (Markdown files)
│   ├── farming/             # Farming posts (Markdown files)
│   ├── music.md             # Single page
│   ├── books.md             # Single page
│   ├── gallery.md           # Gallery page
│   └── about.md             # About page
├── data/
│   └── contributors.yaml    # Contributor bios
├── layouts/
│   ├── _default/
│   │   ├── baseof.html      # Base template (head, nav, footer)
│   │   ├── list.html        # Section list template
│   │   └── single.html      # Single post template
│   ├── blog/                # Blog-specific layouts (if needed)
│   ├── cooking/             # Cooking-specific layouts (if needed)
│   ├── partials/
│   │   ├── header.html
│   │   ├── footer.html
│   │   ├── nav.html
│   │   ├── post-card.html
│   │   └── gallery.html
│   ├── index.html           # Homepage template
│   └── page/
│       └── single.html      # Standalone page template (about, music, books)
├── static/
│   └── images/              # Static images (contributor photos, etc.)
├── hugo.toml                # Hugo site config
├── CNAME                    # GitHub Pages custom domain
├── .github/
│   └── workflows/
│       └── deploy.yml       # GitHub Actions: build Hugo + deploy to Pages
└── README.md
```

---

## Migration Plan

Existing content to migrate from the current static HTML files:

1. **Blog.html** → Individual Markdown files in `content/blog/`
   - Cougar Creek Fire post (8/3/24)
   - Day 2 post (8/4/24)
   - Mount Misery post (8/5/24)
   - Drop the fake/placeholder posts

2. **Cooking.html** → `content/cooking/salchichas-papa.md`
   - Extract recipe content into Markdown with front matter

3. **index.html** → Replaced by Hugo homepage template

4. **CNAME** → Keep as-is in repo root (or `static/CNAME`)

---

## Deployment

1. **GitHub Actions** workflow triggers on push to `main`
2. Hugo builds the site to `public/`
3. Action deploys `public/` to GitHub Pages
4. CNAME ensures almondfarm.us points to the site

---

## Future Enhancements (Out of Scope for v1)

- [ ] Decap CMS integration (browser-based content editing for contributors)
- [ ] Comments system (Giscus or similar GitHub-based comments)
- [ ] RSS feeds per section
- [ ] Search functionality
- [ ] Dark mode toggle
- [ ] Newsletter signup
