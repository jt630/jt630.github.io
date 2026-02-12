# How to Make a Cunty Theme

A reference guide based on the Almond Farm "Maximum Cunty" dark theme. Hot pink, black, and gold.

---

## 1. The Palette

Everything starts with the color variables. Define them in `:root` so they're reusable everywhere.

```css
:root {
  /* Primary accent — HOT PINK */
  --pink: #FF2D8A;
  --pink-light: #FF6DB3;
  --pink-glow: rgba(255, 45, 138, 0.4);

  /* Secondary accent — GOLD */
  --gold: #D4AF37;
  --gold-light: #F5D674;

  /* Backgrounds — PITCH BLACK, layered */
  --black: #0A0A0A;          /* page bg */
  --black-soft: #141414;      /* subtle lift */
  --black-card: #1A1A1A;      /* card bg */
  --black-elevated: #222222;  /* nested elements */

  /* Text — warm off-white, not pure #fff */
  --white: #F5F0EB;
  --white-dim: rgba(245, 240, 235, 0.7);
  --white-faint: rgba(245, 240, 235, 0.4);

  /* Shadows with color */
  --shadow-pink: 0 4px 30px rgba(255, 45, 138, 0.25);
  --shadow-gold: 0 4px 30px rgba(212, 175, 55, 0.2);
}
```

**Key rules:**
- Background is near-black, NOT pure `#000` (too harsh). `#0A0A0A` has just enough warmth.
- Text is warm off-white `#F5F0EB`, not sterile `#FFFFFF`.
- Cards use progressively lighter blacks to create depth without color.
- The glow variables (`rgba` with your accent color) are for `text-shadow` and `box-shadow` hover effects.

---

## 2. Typography

Two fonts, high contrast between them:

```css
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400;1,700;1,900&family=Space+Grotesk:wght@400;500;600;700&display=swap');
```

| Role | Font | Style |
|------|------|-------|
| Headings | **Playfair Display** | Serif, italic, 900 weight |
| Body | **Space Grotesk** | Sans-serif, clean, 400-700 |

```css
h1, h2, h3, h4 {
  font-family: 'Playfair Display', serif;
  font-style: italic;       /* italic headings = drama */
  letter-spacing: -0.02em;  /* tight tracking = editorial */
  line-height: 1.15;
}

body {
  font-family: 'Space Grotesk', sans-serif;
  line-height: 1.7;         /* generous for readability */
}
```

**The vibe:** Italic serif headings feel editorial and luxe. Geometric sans body keeps it modern. The contrast between the two does a lot of the heavy lifting.

---

## 3. The Hero Section

This is the centerpiece. Three layers:

### Shimmer gradient text
```css
.hero h1 {
  font-size: 5rem;
  font-style: italic;
  background: linear-gradient(135deg, var(--pink) 0%, var(--gold-light) 50%, var(--pink-light) 100%);
  background-size: 200% 200%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: shimmer 4s ease infinite;
}

@keyframes shimmer {
  0%   { background-position: 0% 50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
```

### Radial glow backdrop
```css
.hero::before {
  content: '';
  position: absolute;
  top: -50%; left: -50%;
  width: 200%; height: 200%;
  background:
    radial-gradient(ellipse at 30% 50%, rgba(255, 45, 138, 0.12) 0%, transparent 50%),
    radial-gradient(ellipse at 70% 50%, rgba(212, 175, 55, 0.08) 0%, transparent 50%);
  animation: heroGlow 10s ease-in-out infinite alternate;
}

@keyframes heroGlow {
  0%   { transform: translate(0, 0) scale(1); }
  100% { transform: translate(-5%, 3%) scale(1.1); }
}
```

The glow is subtle — 12% and 8% opacity. It slowly drifts. You shouldn't consciously notice it, but the page feels alive.

---

## 4. Cards That Glow

Every card follows the same pattern:

```css
.card {
  background: var(--black-card);
  border: 1px solid rgba(255, 255, 255, 0.06);  /* barely visible border */
  border-radius: 12px;
  transition: all 0.35s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.card:hover {
  transform: translateY(-4px);              /* lift */
  border-color: var(--pink);                /* border lights up */
  box-shadow: var(--shadow-pink);           /* pink glow underneath */
}
```

### Optional: gradient overlay on hover
```css
.card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255, 45, 138, 0.06) 0%, transparent 60%);
  opacity: 0;
  transition: opacity 0.35s;
}

.card:hover::before {
  opacity: 1;
}
```

**Key:** The resting state is almost invisible borders (6% white). On hover, the border goes full pink and a colored shadow appears underneath. The lift + glow + border change together = the card "activates."

---

## 5. Links and Hover States

Everything glows on hover:

```css
a {
  color: var(--pink);
  text-decoration: none;
  transition: color 0.25s, text-shadow 0.25s;
}

a:hover {
  color: var(--pink-light);
  text-shadow: 0 0 16px var(--pink-glow);  /* neon glow */
}
```

The `text-shadow` with `rgba` pink creates a neon sign effect. Don't overdo the blur radius — 12-16px is the sweet spot.

---

## 6. Section Accent Borders

Alternate pink and gold across sections for variety:

```css
.section-card.blog    { border-top: 3px solid var(--pink); }
.section-card.cooking { border-top: 3px solid var(--gold); }
.section-card.music   { border-top: 3px solid var(--pink-light); }
.section-card.books   { border-top: 3px solid var(--gold-light); }
```

### Gradient side-bars on subheadings
```css
.curated-page h2 {
  color: var(--gold);
  padding-left: 1rem;
  position: relative;
}

.curated-page h2::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.15em; bottom: 0.15em;
  width: 3px;
  background: linear-gradient(180deg, var(--pink), var(--gold));
  border-radius: 2px;
}
```

---

## 7. Custom Scrollbar + Selection

Tiny details that sell the whole thing:

```css
/* Pink scrollbar */
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: var(--black); }
::-webkit-scrollbar-thumb { background: var(--pink); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--pink-light); }

/* Pink text selection */
::selection {
  background: var(--pink);
  color: var(--white);
}
```

---

## 8. Nav

Sticky, blurred backdrop, pill-shaped links:

```css
.site-nav {
  background: var(--black);
  position: sticky;
  top: 0;
  z-index: 100;
  border-bottom: 1px solid rgba(255, 45, 138, 0.15);
  backdrop-filter: blur(12px);
}

.nav-links a {
  padding: 0.45rem 0.85rem;
  border-radius: 999px;           /* pill shape */
  border: 1px solid transparent;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  font-size: 0.88rem;
}

.nav-links a:hover {
  color: var(--pink);
  border-color: var(--pink);
  text-shadow: 0 0 12px var(--pink-glow);
  background: rgba(255, 45, 138, 0.08);
}
```

The brand name is bold italic Playfair in pink. It scales up slightly on hover with a glow.

---

## 9. Mobile

Hamburger menu with three pink bars. Nav slides down as a full-width panel:

```css
@media (max-width: 768px) {
  .nav-links {
    display: none;
    flex-direction: column;
    position: absolute;
    top: 64px;
    left: 0; right: 0;
    background: var(--black);
    border-bottom: 1px solid rgba(255, 45, 138, 0.15);
  }

  .nav-links.open { display: flex; }
  .nav-toggle { display: block; }
}
```

Toggle with one line of JS:
```js
document.querySelector('.nav-toggle')?.addEventListener('click', function() {
  document.querySelector('.nav-links').classList.toggle('open');
});
```

---

## 10. The Principles

1. **Black background, colored accents only.** Never add a third accent color. Pink and gold is enough.
2. **Glow > color fill.** Hover states use `text-shadow` and `box-shadow` with the accent color at low opacity, not solid background changes.
3. **Layered blacks for depth.** `#0A0A0A` -> `#1A1A1A` -> `#222222`. No grays.
4. **Italic serif headings.** This single choice does 80% of the aesthetic work.
5. **Transitions on everything.** `0.25s-0.35s` with a smooth cubic-bezier. Nothing should snap.
6. **Borders start invisible, activate on hover.** Resting state = `rgba(255,255,255,0.06)`. Hover = full accent color.
7. **Warm white text.** `#F5F0EB` not `#FFFFFF`. Dim and faint variants at 70% and 40% opacity for hierarchy.
8. **Details matter.** Scrollbar, text selection, border-top color per section — these small things make it feel intentional.

---

## File Structure (Hugo)

```
assets/css/main.css          <- all the styles, one file
layouts/_default/baseof.html  <- loads the CSS via Hugo pipes
layouts/partials/nav.html     <- nav with hamburger
layouts/partials/footer.html  <- footer with pink border-top
layouts/index.html            <- hero + section cards + recent posts
```

The CSS is loaded through Hugo's asset pipeline:
```html
{{ $css := resources.Get "css/main.css" }}
<link rel="stylesheet" href="{{ $css.RelPermalink }}">
```

No build tools, no Sass, no Tailwind. One CSS file with custom properties.
