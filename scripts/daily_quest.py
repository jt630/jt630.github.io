#!/usr/bin/env python3
"""
Almond Farm Quest Board
Roll three dice to get your next gamified content mission.

    D8  — Category (what domain to work in)
    D4  — Size (scope of the task)
    D6  — Twist (a modifier/constraint)

Usage:
  python3 scripts/daily_quest.py              # random roll
  python3 scripts/daily_quest.py 4 2 5        # force specific rolls (cat size twist)
"""

import random
import sys
import textwrap

# ─── ANSI Colors ─────────────────────────────────────────────────────────────

PINK   = "\033[38;2;255;45;138m"
GOLD   = "\033[38;2;212;175;55m"
WHITE  = "\033[97m"
GRAY   = "\033[90m"
DGRAY  = "\033[38;2;60;60;60m"
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

# ─── D8: Categories ──────────────────────────────────────────────────────────

CATEGORIES = {
    1: {
        "name": "NARRATIVE",
        "emoji": "📖",
        "section": "blog",
        "base_xp": 50,
        "quests": [
            {
                "name": "The Chronicler's Call",
                "prompt": (
                    "Write a blog post about something real — a small observation from this week, "
                    "a weird thought you've been sitting with, something that surprised you. "
                    "300-500 words. The topic doesn't matter. Getting it out does."
                ),
            },
            {
                "name": "The Pitch Deck",
                "prompt": (
                    "Write up a business idea. The idea, the problem it solves, who it's for, "
                    "and why YOU specifically could pull it off. 200-400 words. "
                    "Be honest about what's still missing."
                ),
            },
            {
                "name": "Stream of Consciousness",
                "prompt": (
                    "No topic assigned. Open a new post and just write. Don't edit. Don't plan. "
                    "Set a 15-minute timer and go. Publish whatever you wrote. "
                    "Imperfect and honest beats polished and empty."
                ),
            },
        ],
    },
    2: {
        "name": "COOKING",
        "emoji": "🍳",
        "section": "cooking",
        "base_xp": 55,
        "quests": [
            {
                "name": "The Chef's Table",
                "prompt": (
                    "Drop a recipe. Something you've actually made. Ingredients list, numbered steps, "
                    "and one personal note about what makes it yours. "
                    "Don't write a cookbook — write a note to a friend."
                ),
            },
            {
                "name": "The Flavor Diary",
                "prompt": (
                    "Write about a meal you ate recently that was worth remembering. "
                    "Where was it? What made it good? What would you change? "
                    "A photo if you have one. A craving if you don't."
                ),
            },
            {
                "name": "The Bartender's Secret",
                "prompt": (
                    "Add a drink recipe to the site. Cocktail, mocktail, coffee ritual, tea ceremony — "
                    "your call. Include ratios, method, and what occasion it fits. "
                    "Bonus if it has a good name and a short origin story."
                ),
            },
        ],
    },
    3: {
        "name": "FARMING",
        "emoji": "🌱",
        "section": "farming",
        "base_xp": 45,
        "quests": [
            {
                "name": "Field Dispatch",
                "prompt": (
                    "Write a farming or garden update. What's growing, what died, what you're planning. "
                    "Include the date and season. Think of it as a letter to your future self — "
                    "what do you want to remember about this moment on the land?"
                ),
            },
            {
                "name": "Soil Report",
                "prompt": (
                    "Pick one specific plant, crop, or area of the farm/garden and write a deep dive. "
                    "Its history here, what worked, what didn't, what you're changing. "
                    "This is institutional memory. Write it down."
                ),
            },
        ],
    },
    4: {
        "name": "TECHNICAL",
        "emoji": "⚗️",
        "section": "technical",
        "base_xp": 100,
        "quests": [
            {
                "name": "API Alchemy",
                "prompt": (
                    "Connect to an external API and display the data somewhere on the site. "
                    "Ideas: weather for the farm, GitHub commit stats, a random word/quote, "
                    "Spotify track, sunset time. Use a Hugo data fetch or build-time script."
                ),
            },
            {
                "name": "The Optimizer",
                "prompt": (
                    "Pick one thing that annoys you about the site — broken mobile layout, slow page, "
                    "missing meta tags, awkward navigation, an empty section. "
                    "Diagnose it, fix it, document what you found."
                ),
            },
            {
                "name": "Infinite Operator",
                "prompt": (
                    "Work on the Infinite Monkey Theorem project. Read MONKEYS.md first, "
                    "then pick one component and advance it: dictionary file, registry entry, "
                    "mint script, coin template. Small, real progress counts."
                ),
            },
        ],
    },
    5: {
        "name": "VISUAL",
        "emoji": "🖼️",
        "section": "gallery",
        "base_xp": 60,
        "quests": [
            {
                "name": "Gallery Drop",
                "prompt": (
                    "Add something visual to the site. Photos, scans, drawings, screenshots — "
                    "anything you'd put on a wall. At least 3 images. "
                    "Drop them in static/images/gallery/ with short, honest alt text."
                ),
            },
            {
                "name": "The Stylist",
                "prompt": (
                    "Improve one visual thing on the site. Font pairing, spacing, color, "
                    "mobile layout, hover effects, the footer, the nav. "
                    "Pick the one thing that bothers you most and make it better. Ship it."
                ),
            },
            {
                "name": "Lab Rat",
                "prompt": (
                    "Brain Lab experiment time. Pick something in the CSS or UX and try something weird — "
                    "a new hover effect, a typographic experiment, an animation, a layout shift. "
                    "It doesn't have to be good. It has to be interesting. Document it."
                ),
            },
        ],
    },
    6: {
        "name": "POP CULTURE",
        "emoji": "🎬",
        "section": "movies / gaming / drinks",
        "base_xp": 50,
        "quests": [
            {
                "name": "Reel Talk",
                "prompt": (
                    "Write a movie or TV review. One you've watched recently or one you want "
                    "more people to know about. No plot summaries — just your honest take. "
                    "What hit, what didn't, who should watch it."
                ),
            },
            {
                "name": "Player One",
                "prompt": (
                    "Write about a game. Currently playing, recently finished, or a classic you return to. "
                    "Not a formal review — what would you tell a friend about it over a beer? "
                    "Hook, vibe, worth it or not?"
                ),
            },
            {
                "name": "Side B",
                "prompt": (
                    "Write about a piece of music that's been living in your head lately. "
                    "An album, an artist, a specific song. What's the feeling it gives you? "
                    "When do you reach for it? Why does it matter?"
                ),
            },
        ],
    },
    7: {
        "name": "NEW TERRITORY",
        "emoji": "🏗️",
        "section": "new",
        "base_xp": 90,
        "quests": [
            {
                "name": "The Architect",
                "prompt": (
                    "Pick one empty section (gaming, art, movies, drinks, body, gadgets) "
                    "and build it out properly. What goes in it? What does the list page look like? "
                    "Write one real first post for it. Make it feel like it was always meant to be there."
                ),
            },
            {
                "name": "Data Cartographer",
                "prompt": (
                    "Design a brand-new data-driven section. Study how music.md and books.md work "
                    "(data YAML → Hugo template → rendered page). Now do it for a new domain: "
                    "movies, gear, restaurants, plants, records. Schema, template, 5 seed entries, live page."
                ),
            },
            {
                "name": "Body Report",
                "prompt": (
                    "The body section is empty. Fill it. Write something about movement, health, "
                    "physical practice — what you're training for, what's working, what isn't. "
                    "This is a log, not a tutorial. Be real about where you actually are."
                ),
            },
        ],
    },
    8: {
        "name": "WILD CARD",
        "emoji": "🃏",
        "section": "any",
        "base_xp": 75,
        "quests": [
            {
                "name": "The Joker's Hand",
                "prompt": (
                    "No assignment. Build something you've been thinking about but haven't started. "
                    "It doesn't have to fit anywhere. It just has to be real. "
                    "Write it, code it, ship it. No rules today."
                ),
            },
            {
                "name": "Double Down",
                "prompt": (
                    "Roll twice more and do BOTH quests this session. "
                    "Run /roll again to get your second assignment. "
                    "Find where the two quests connect — there's always a thread."
                ),
            },
            {
                "name": "The Time Capsule",
                "prompt": (
                    "Write a post dated one year from today. Predictions, intentions, hopes, "
                    "things you want to remember to do. Set it to publish as a draft. "
                    "Come back to it in twelve months."
                ),
            },
        ],
    },
}

# ─── D4: Sizes ────────────────────────────────────────────────────────────────

SIZES = {
    1: {
        "name": "Quick Hit",
        "time": "15-30 min",
        "emoji": "⚡",
        "desc": "Get something live. Imperfect and shipped beats perfect and draft.",
        "xp_mult": 0.75,
    },
    2: {
        "name": "Standard",
        "time": "1-2 hrs",
        "emoji": "🎯",
        "desc": "A full piece. Take your time but stay focused.",
        "xp_mult": 1.0,
    },
    3: {
        "name": "Deep Dive",
        "time": "2-4 hrs",
        "emoji": "🔬",
        "desc": "Something substantial. Research, draft, iterate, publish.",
        "xp_mult": 1.5,
    },
    4: {
        "name": "Epic Quest",
        "time": "open scope",
        "emoji": "🏆",
        "desc": "Ambitious. Set your own timeline. This one goes in the portfolio.",
        "xp_mult": 2.0,
    },
}

# ─── D6: Twists ───────────────────────────────────────────────────────────────

TWISTS = {
    1: {
        "name": "Clean Run",
        "emoji": "🎯",
        "desc": "No modifiers. Just do the quest.",
        "xp_bonus": 0,
    },
    2: {
        "name": "Speed Run",
        "emoji": "⚡",
        "desc": "Complete it in under 30 minutes. Speed bonus active. Ship fast, ship now.",
        "xp_bonus": 25,
    },
    3: {
        "name": "Visuals Required",
        "emoji": "📸",
        "desc": "Must include at least one image or visual element. No image = no XP.",
        "xp_bonus": 15,
    },
    4: {
        "name": "Cross-Link",
        "emoji": "🔗",
        "desc": "Link this new content to something that already exists on the site.",
        "xp_bonus": 20,
    },
    5: {
        "name": "Data Mode",
        "emoji": "📊",
        "desc": "Store part of this in YAML. Make it data-driven. Config over content.",
        "xp_bonus": 30,
    },
    6: {
        "name": "Ship Today",
        "emoji": "🚀",
        "desc": "No drafts. This goes live today. Done is better than perfect.",
        "xp_bonus": 10,
    },
}

# ─── Display ──────────────────────────────────────────────────────────────────

W = 62  # terminal width


def line(char="─"):
    return f"{PINK}{char * W}{RESET}"


def wrap(text, indent=2):
    return textwrap.fill(
        text,
        width=W - indent,
        initial_indent=" " * indent,
        subsequent_indent=" " * indent,
    )


def display_quest(cat_roll, size_roll, twist_roll):
    category = CATEGORIES[cat_roll]
    size = SIZES[size_roll]
    twist = TWISTS[twist_roll]
    quest = random.choice(category["quests"])

    base_xp = category["base_xp"]
    scaled_xp = int(base_xp * size["xp_mult"])
    total_xp = scaled_xp + twist["xp_bonus"]

    print()
    print(line("━"))
    print(f"{BOLD}{PINK}{'ALMOND FARM  ·  QUEST BOARD':^{W}}{RESET}")
    print(f"{DGRAY}{'roll the dice — earn the XP':^{W}}{RESET}")
    print(line("━"))
    print()

    # Dice rolls
    print(f"  {DIM}D8  CATEGORY {RESET}  {PINK}{cat_roll:>2}{RESET}  {category['emoji']}  {BOLD}{category['name']}{RESET}")
    print(f"  {DIM}D4  SIZE     {RESET}  {PINK}{size_roll:>2}{RESET}  {size['emoji']}  {BOLD}{size['name']}{RESET}  {GRAY}({size['time']}){RESET}")
    print(f"  {DIM}D6  TWIST    {RESET}  {PINK}{twist_roll:>2}{RESET}  {twist['emoji']}  {BOLD}{twist['name']}{RESET}")
    print()
    print(line())

    # Quest name
    print()
    print(f"  {GOLD}{BOLD}{quest['name'].upper()}{RESET}")
    print()

    # Prompt
    print(f"{WHITE}{wrap(quest['prompt'])}{RESET}")
    print()

    # Twist block
    print(f"  {GOLD}TWIST ·{RESET} {twist['emoji']} {BOLD}{twist['name']}{RESET}")
    print(f"{GRAY}{wrap(twist['desc'])}{RESET}")
    print()

    # Size block
    print(f"  {GOLD}SCOPE ·{RESET} {size['emoji']} {BOLD}{size['name']}{RESET}  {GRAY}— {size['desc']}{RESET}")
    print()

    # Section hint
    print(f"  {DGRAY}Section hint:  content/{category['section']}/{RESET}")
    print()

    # XP summary
    print(line())
    xp_line = f"  {GOLD}{BOLD}TOTAL XP  {total_xp} ★{RESET}"
    if twist["xp_bonus"] > 0:
        xp_line += f"  {GRAY}(base {scaled_xp} + {twist['xp_bonus']} twist){RESET}"
    print(xp_line)
    print(line("━"))
    print()


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if len(args) == 3:
        try:
            cat_roll   = int(args[0])
            size_roll  = int(args[1])
            twist_roll = int(args[2])
            if not (1 <= cat_roll <= 8 and 1 <= size_roll <= 4 and 1 <= twist_roll <= 6):
                raise ValueError
        except ValueError:
            print("Usage: daily_quest.py [cat(1-8) size(1-4) twist(1-6)]")
            sys.exit(1)
    elif len(args) == 0:
        cat_roll   = random.randint(1, 8)
        size_roll  = random.randint(1, 4)
        twist_roll = random.randint(1, 6)
    else:
        print("Usage: daily_quest.py [cat(1-8) size(1-4) twist(1-6)]")
        sys.exit(1)

    display_quest(cat_roll, size_roll, twist_roll)


if __name__ == "__main__":
    main()
