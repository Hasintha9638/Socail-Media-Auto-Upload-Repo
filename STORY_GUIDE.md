# Tiny Tales Daily — writing guide (moral stories, tiny motivation, funny motivation, life lessons, zen stories)

Channel name: **Tiny Tales Daily** (YouTube + TikTok). Use this exact name in end cards and descriptions.

Each day: write ONE new story as `stories/YYYY-MM-DD-<slug>.json`, preview it, commit it to `main`.
GitHub Actions renders it and uploads it to YouTube Shorts (goes live 6:30 PM Asia/Colombo).

## Content formats: rotate daily (pick by day of month: day % 5)
| day % 5 | Format | What it is | Example hook |
|---|---|---|---|
| 0 | **Moral story** | A fable with a twist and a moral card | "Every morning, a poor farmer carried one stone…" |
| 1 | **Tiny motivation** | 35–45 s. One character, one struggle, one breakthrough. Punchy lines, no "once upon a time". Ends on a bold one-line quote card | "He failed 99 times. The 100th try took 4 seconds." |
| 2 | **Funny motivation** | 35–50 s. Comic setup (lazy goat, overconfident rooster, a snail in a race, a cat who "starts Monday"), a silly escalation, a punchline, then a real lesson. Light, kind humour, never mocking real people | "Every Monday, the cat promised to start his diet. This is Monday number 412." |
| 4 | **Zen story** | 40–55 s, calm and slow (`speed` 0.88, `mood` "sad" or "warm", voice bm_george or bf_emma). A master and a student (or a monk and a visitor) with a short exchange and a quiet, surprising insight. Visuals: misty mountains, moonlit or dawn skies, a monk with a staff (`kind: old`, `staff: true`), still water, few elements. You may retell a classic traditional Zen parable **in your own words** (say "a classic Zen story" in the description), or write an original one in that spirit. Never copy a published translation word for word. End card: the insight in one calm line | "A student asked the master: how long until I find peace?" |
| 3 | **Life lesson** | 40–55 s. An everyday situation (money, friends, phone habits, parents, comparison, patience) told as a short tale with a sharp takeaway | "Two brothers got the same 100 rupees. One was broke by Friday." |
Check stories/PUBLISHED.md so the last 3 videos weren't the same format or theme.

## SEO + trending rules (every video)
- **YouTube title (≤ 60 chars, then hashtags):** put a search keyword near the start plus a curiosity gap, then ` #shorts` plus 1–2 topic tags.
  Patterns: "He Laughed at the Lazy Goat… Then This Happened #shorts #motivation", "The 100 Rupee Life Lesson Nobody Teaches #shorts #lifelessons", "One Stone a Day Changed Everything | Moral Story #shorts".
- **Keywords to rotate:** zen story, zen wisdom, mindfulness, motivation, motivational story, life lessons, moral story, short story, animated story, funny motivation, self improvement, discipline, success mindset, kindness, inspiration.
- **Description:** line 1 is a keyword-rich hook sentence (shown in search), then the moral, then the Tiny Tales Daily subscribe line, then **5–8 hashtags** with the format's tags first:
  - moral: #moralstory #shortstory #animatedstory #lifelessons #TinyTalesDaily #shorts
  - tiny motivation: #motivation #motivationalvideo #successmindset #discipline #TinyTalesDaily #shorts
  - funny motivation: #funnymotivation #funny #motivation #relatable #TinyTalesDaily #shorts
  - life lesson: #lifelessons #lifeadvice #selfimprovement #wisdom #TinyTalesDaily #shorts
  - zen story: #zenstory #zen #mindfulness #wisdom #innerpeace #TinyTalesDaily #shorts (title example: "Empty Your Cup First | Zen Story #shorts #zen")
- **tags field:** 10–15 tags. Mix broad (motivation, short story) with specific (the story's theme, e.g. "patience story", "lazy goat story").
- **Hooks decide reach:** the first line must create a question in 2 seconds. Keep videos under 50 s, because rewatches count, and end on a line that makes people comment, like, or share (a question or a quotable line).
- Topical but evergreen: you may echo what's trending (exams season, New Year goals, monsoon, cricket season in Sri Lanka) but never copy anyone's video, song, or character.

## What makes a hit (follow every time)
1. **Hook in the first line (under 3 s).** Open with a strange action or stakes, never "Once upon a time".
   Good: "Every morning, a poor farmer carried one stone to the edge of his field."
2. **One clear conflict**, usually doubters, a test or a temptation, then a **turn** that rewards the patient, kind or honest choice.
3. **Twist or payoff in the second-to-last scene**, and the **moral as the last line** (one sentence, quotable, under 14 words).
4. **110–140 words of narration**, 6–8 scenes, 40–58 seconds in total. Short sentences you can read aloud.
5. **Original stories only.** Don't retell famous fables word for word (no "boy who cried wolf" or "cracked pot"). Inspiration is fine, but the plot, characters and line wording must be new. YouTube demonetizes repetitive or mass-produced content, so vary the setting, the characters, the structure and the type of moral.
6. **Title:** curiosity gap plus outcome, under 70 characters, then ` #shorts #moralstory`.
   Pattern: "He Did X Every Day… Then Y Happened", "The King Laughed at the Beggar's Gift — Until…".
7. Before writing, check `stories/` and `stories/PUBLISHED.md`. **Don't repeat a theme used in the last 14 days.**
   Rotate morals: patience, honesty, kindness returned, greed punished, humility, gratitude, courage, hard work, forgiveness, wisdom over strength, listening, sharing, not judging by looks, and consistency.

## JSON shape
```json
{
  "title": "...", "youtube_title": "...", "description": "...(story teaser, moral, then \"A new tiny tale every day on Tiny Tales Daily. Subscribe so you don't miss tomorrow's story.\", then 5-6 hashtags incl. #TinyTalesDaily)",
  "tags": ["moral story", "..."],
  "voice": "bm_george",            // also: bm_lewis, am_michael, bf_emma, af_heart (vary by story)
  "speed": 0.95, "mood": "warm",   // mood: warm | sad | hopeful
  "highlight": ["words", "shown", "in", "yellow"],
  "scenes": [ { "narration": "...", "elements": [ ... ], "camera": {...}, ... } ]
}
```
Scene options: `caption_y` (640 default), `captions` (false on the moral card), `lead`/`tail` seconds of silence,
`sfx_rain` (0–1), `dark` (0–1 extra night grading), `camera: {zoom, cx, cy}`.

**Keyframes:** any number can be `[[t0, v0], [t1, v1], ...]` with t from 0 to 1 over the scene (eased).

**Canvas:** 1080×1920, ground line y=1450. Keep people and props between x=80 and x=1000. Shorts UI covers y>1650, so keep nothing important there.
Captions sit around y=640, so keep the sky area y=520–780 free of busy elements.

### Elements (drawn in list order, back to front)
| type | key params |
|---|---|
| sky | `preset`: dawn, day, golden, dusk, night, storm, card · or `top`/`bottom` hex · `cycle: N` = N fast day/night cycles (time passing) |
| sun / moon | `x`, `y`, `r`, `color` · `cycle_arc: true` with a cycling sky |
| stars | `alpha` |
| clouds | `count`, `color`, `alpha`, `y: [min,max]`, `speed`, `seed` |
| birds | `count`, `y` |
| hills | `color`, `base_y` (≈1210 far, 1340 near), `amp`, `seed` |
| houses | `items: [[x, y, scale]]`, `color`, `window`, `lit` |
| palms / trees | `items: [[x, y_ground, scale]]`, `color`, `seed` |
| ground | `color`, `furrow`, `grass_color`, `furrows`, `riverbed: [x_end, depth]` (river dip on the left) |
| water | `level` (y), `x1` (right edge), `color`, `top`, `rough` |
| wall | `x0`, `x1`, `height`, `fill` 0–1 (stone-by-stone growth), `seed` |
| person | `kind`: farmer, old, villager, villager_f, child · `anim`: idle, walk, carry, laugh, wave, sit · `x` (keyframe it to walk), `y`, `s`, `facing` ±1, `bend` 0–1, `holding` (carry), `staff`, `color`, `show: [t0, t1]` |
| rain | `intensity` · lightning: `times: [seconds]` (thunder is added automatically) |
| splash | `x`, `y`, `intensity` |
| fireflies | `count`, `y` |
| text | `text`, `y`, `size`, `color`, `stroke`, `serif`, `alpha`, `counter: {value, fmt: "YEAR {}"}` |

### Recurring patterns
- **Scene 1:** the hook action, plus a gold title `text` at y=250 that fades out.
- **Time passing:** `sky.cycle: 3` + sun/moon `cycle_arc` + a `counter` text.
- **Last scene (moral card):** `sky: card`, stars, moon, dark silhouettes, `captions: false`, serif `text` with the moral at y=640, and the gold line "Tiny Tales Daily  •  New story every day" at y=900. Use `lead: 0.6`, `tail: 2.2`.
- Use the same background layers in every scene of a story so the place feels continuous. Change only the colours for time of day and weather.
- Match colour palettes to the mood: warm dawn and golden for hope, cold blue night and storm for danger.

## Before committing (required)
1. `python storykit/storykit.py --stills stories/<file>.json prev 0:2 1:3 2:4 ...` and **look at every frame**.
   Check that captions don't collide with the title, people stand on the ground, nothing is cut off, and the scene reads clearly at small size.
2. Optional full render: `python storykit/storykit.py stories/<file>.json out/test.mp4` (~3 min).
3. Commit only the JSON: `git add stories/<file>.json && git commit -m "Story: <title>" && git push`.
