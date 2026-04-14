Roll the Almond Farm quest dice and assign a gamified content mission.

Run this command and display the full output to the user:

```bash
python3 scripts/daily_quest.py
```

After showing the output, ask the user one question:
**"Ready to start this quest? I can kick it off — open a new post, scaffold a file, or outline the first steps."**

If they say yes or want to start:
- For content quests (blog, cooking, farming, pop culture, body): offer to run `/new-post` to scaffold the file
- For technical quests: outline the first 2-3 concrete steps and ask which to tackle first
- For visual/design quests: read the relevant CSS or template file first, then propose a specific change
- For new territory quests: read CLAUDE.md to understand the site structure, then draft a plan

If the quest is "Double Down", run `python3 scripts/daily_quest.py` a second time immediately to give the user their second assignment.

The user can also pass specific rolls to test a particular combo:
```bash
python3 scripts/daily_quest.py 4 3 2   # cat=4 (Technical), size=3 (Deep Dive), twist=2 (Speed Run)
```
