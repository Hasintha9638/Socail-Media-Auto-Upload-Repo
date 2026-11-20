# Mindset Minute — writing guide (moral stories, tiny motivation, funny motivation, zen stories, success tips, life lessons)

Channel name: **Mindset Minute** (YouTube + TikTok + Facebook; renamed from Tiny Tales Daily on 2026-11-19). Use this exact name in end cards and descriptions. Never write "Tiny Tales Daily" in new stories.

Each day: write ONE new story as `stories/YYYY-MM-DD-<slug>.json`, preview it, commit it to `main`.
GitHub Actions renders it and schedules it on YouTube Shorts for the US evening peak (5:45 AM Sri Lanka next morning = 7:15 PM New York); Facebook Reels post at the same time.

## Two videos a day
Each daily run writes **two** stories, committed together in ONE commit:
| File | Slot | `publish_at` | `publish_date` | Goes live |
|---|---|---|---|---|
| `stories/<D>-a-<slug>.json` | US evening | `"05:45"` | D+1 | 5:45 AM Sri Lanka = 7:15 PM New York |
| `stories/<D>-b-<slug>.json` | US morning | `"18:45"` | D+1 | 6:45 PM Sri Lanka = 8:15 AM New York |
D = today's date in Asia/Colombo. Both JSONs carry `"publish_at"` and `"publish_date"`.
Story a takes the next format in the rotation, and story b the one after it. Give them different themes, characters and settings, so the two videos of a day never feel alike.

## Content formats: rotate in this order
These eight formats get the most views on Shorts. Each story JSON must include `"format": "<name>"`. Look at the newest story in `stories/` (by file name): the next video's format is the **next one after its format** in this list (wrap around; if the newest has another or no `format`, start at Success tips).

| # | Format | What it is | Example hook |
|---|---|---|---|
| 1 | **Success tips** | 62–75 s. "3 things/habits/rules…" style, told through one animated character's day (a student, a shopkeeper, a young farmer) — each tip shown as a big numbered `text` element (e.g. "1. Start before you're ready") while the scene acts it out. Practical, specific, no hype or get-rich promises. End card: the one tip to remember | "3 habits that quietly made a poor boy rich." |
| 2 | **Tiny motivation** | 62–70 s. One character, one struggle, one breakthrough. Punchy lines, no "once upon a time". Ends on a bold one-line quote card | "He failed 99 times. The 100th try took 4 seconds." |
| 3 | **Zen story** | 62–75 s, calm and slow (`speed` 0.88, `mood` "sad" or "warm", voice bm_george). A master and a student (or a monk and a visitor) with a short exchange and a quiet, surprising insight. Visuals: misty mountains, moonlit or dawn skies, a monk with a staff (`kind: old`, `staff: true`), still water, few elements. You may retell a classic traditional Zen parable **in your own words** (say "a classic Zen story" in the description), or write an original one in that spirit. Never copy a published translation word for word. End card: the insight in one calm line | "A student asked the master: how long until I find peace?" |
| 4 | **Rich vs Poor mindset** | 62–72 s split screen: a `divider` at x=540, a red-boxed "POOR MINDSET" label (`x`: 270, `box`: "#c0392b") and a green-boxed "RICH MINDSET" label (`x`: 810, `box`: "#1e8449"), one character on each side reacting to the same situation (payday, a free hour, a failure, criticism, a new skill, a phone at midnight). 3–4 contrasts, each its own scene, then a one-line takeaway card. It's about **thinking and habits** (spending vs investing in skills, blaming vs learning, consuming vs creating), never shaming people with little money, and no promises of getting rich or advice to buy any investment | "Payday. Poor mindset: 'Time to treat myself.' Rich mindset: 'Time to pay myself first.'" |
| 5 | **Stoic wisdom** | 62–72 s. One Stoic idea (Marcus Aurelius, Seneca, Epictetus: their ideas are centuries old, so short quotes are fine; credit the name) shown as a tiny modern scene: someone stuck in traffic, insulted, failing a test, then reframing it. Calm, confident voice (bm_george). End card: the idea in one line with the philosopher's name | "Marcus Aurelius ruled Rome. Every morning he told himself one strange thing." |
| 6 | **Grandpa's life advice** | 62–75 s. An old man (`kind: old`) shares 3 short lessons with a child or grandchild (`kind: child` / `student`), warm and emotional, ending on the most touching one. Warm music (`mood` "warm"). Never mention illness or death graphically: "before he passed" at most | "My grandfather gave me three rules. I ignored the third one. Big mistake." |
| 7 | **Discipline: Day 1 vs Day 365** | 62–72 s. One habit (running, studying, saving, waking early, reading) shown as Day 1 → Day 30 → Day 100 → Day 365 with a big `counter` text, the character visibly improving (posture, pose `cheer`), small setbacks included. End: "Motivation starts it. Discipline finishes it." style line | "Day 1: he couldn't run for two minutes. Day 365…" |
| 8 | **Smart money lessons** | 62–75 s. A wise parent (`kind: old` or `villager`) teaches a child or young adult simple money habits: pay yourself first, wants vs needs, avoid debt for things that lose value, invest in skills. Specific and practical, everyday prices, no get-rich promises, no stocks/crypto/investment product advice, no "guaranteed" anything | "My dad gave me 100 dollars and one rule. I still follow it." |
Also check stories/PUBLISHED.md so the theme differs from the last 6 videos. (Moral story, Funny motivation and Life lesson are retired from the rotation; use only when asked.)

## SEO + trending rules (every video)
- **YouTube title (≤ 60 chars, then hashtags):** put a search keyword near the start plus a curiosity gap, then ` #shorts` plus 1–2 topic tags.
  Patterns: "He Laughed at the Lazy Goat… Then This Happened #shorts #motivation", "The 100 Rupee Life Lesson Nobody Teaches #shorts #lifelessons", "One Stone a Day Changed Everything | Moral Story #shorts".
- **Keywords to rotate:** success tips, habits of successful people, zen story, zen wisdom, mindfulness, motivation, motivational story, life lessons, moral story, short story, animated story, funny motivation, self improvement, discipline, success mindset, kindness, inspiration.
- **Description:** line 1 is a keyword-rich hook sentence (shown in search), then the moral, then the Mindset Minute subscribe line, then **5–8 hashtags** with the format's tags first:
  - moral: #moralstory #shortstory #animatedstory #lifelessons #MindsetMinute #shorts
  - tiny motivation: #motivation #motivationalvideo #successmindset #discipline #MindsetMinute #shorts
  - funny motivation: #funnymotivation #funny #motivation #relatable #MindsetMinute #shorts
  - life lesson: #lifelessons #lifeadvice #selfimprovement #wisdom #MindsetMinute #shorts
  - success tips: #successtips #success #habits #selfimprovement #motivation #MindsetMinute #shorts (title example: "3 Habits That Made a Poor Boy Rich #shorts #success")
  - rich vs poor mindset: #richmindset #mindset #successmindset #moneymindset #selfimprovement #MindsetMinute #shorts (title example: "Poor Mindset vs Rich Mindset on Payday #shorts #mindset")
  - stoic wisdom: #stoicism #stoic #marcusaurelius #mindset #wisdom #MindsetMinute #shorts
  - grandpa's life advice: #lifeadvice #lifelessons #grandpa #wisdom #motivation #MindsetMinute #shorts
  - discipline day 1 vs 365: #discipline #habits #consistency #selfimprovement #motivation #MindsetMinute #shorts
  - smart money lessons: #moneylessons #personalfinance #moneytips #financialliteracy #mindset #MindsetMinute #shorts
  - zen story: #zenstory #zen #mindfulness #wisdom #innerpeace #MindsetMinute #shorts (title example: "Empty Your Cup First | Zen Story #shorts #zen")
- **tags field:** 10–15 tags. Mix broad (motivation, short story) with specific (the story's theme, e.g. "patience story", "lazy goat story").
- **Hooks decide reach:** the first line must create a question in 2 seconds. Keep videos under 50 s, because rewatches count, and end on a line that makes people comment, like, or share (a question or a quotable line).
- Topical but evergreen: you may echo what's trending (exams season, New Year goals, monsoon, cricket season in Sri Lanka) but never copy anyone's video, song, or character.

## What makes a hit (follow every time)
1. **Hook in the first line (under 3 s).** Open with a strange action or stakes, never "Once upon a time".
   Good: "Every morning, a poor farmer carried one stone to the edge of his field."
2. **One clear conflict**, usually doubters, a test or a temptation, then a **turn** that rewards the patient, kind or honest choice.
3. **Twist or payoff in the second-to-last scene**, and the **moral as the last line** (one sentence, quotable, under 14 words).
4. **150–175 words of narration**, 7–9 scenes, **62–75 seconds in total** (TikTok only pays for videos over 1 minute). The renderer holds the last card longer if a story comes out under 62 s, but write enough story to fill the time: never pad with filler. Short sentences you can read aloud.
5. **Original stories only.** Don't retell famous fables word for word (no "boy who cried wolf" or "cracked pot"). Inspiration is fine, but the plot, characters and line wording must be new. YouTube demonetizes repetitive or mass-produced content, so vary the setting, the characters, the structure and the type of moral.
6. **Title:** curiosity gap plus outcome, under 70 characters, then ` #shorts #moralstory`.
   Pattern: "He Did X Every Day… Then Y Happened", "The King Laughed at the Beggar's Gift — Until…".
7. Before writing, check `stories/` and `stories/PUBLISHED.md`. **Don't repeat a theme used in the last 14 days.**
   Rotate morals: patience, honesty, kindness returned, greed punished, humility, gratitude, courage, hard work, forgiveness, wisdom over strength, listening, sharing, not judging by looks, and consistency.

## JSON shape
```json
{
  "title": "...", "youtube_title": "...", "description": "...(story teaser, moral, then \"A new one-minute lesson every day on Mindset Minute. Subscribe so you don't miss tomorrow's story.\", then 5-6 hashtags incl. #MindsetMinute)",
  "tags": ["moral story", "..."],
  "voice": "bm_george",            // also: bm_lewis, am_michael, bf_emma, af_heart (vary by story) — see "Narrator voice" below
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
| person | Flat-cartoon people with faces. `kind`: farmer (straw hat, sarong), old (white hair, beard, staff), monk (orange robe), villager, villager_f (dress, bun), child, student (backpack) · `anim`: idle, walk, carry, laugh, wave, cheer, think, sit · optional colours `skin`, `shirt`, `pants`, `hair` (hex) · `silhouette: true` + `color` for dark night/moral-card silhouettes · `x` (keyframe it to walk), `y`, `s`, `facing` ±1, `bend` 0–1, `holding` (carry), `staff`, `color`, `show: [t0, t1]` |
| rain | `intensity` · lightning: `times: [seconds]` (thunder is added automatically) |
| splash | `x`, `y`, `intensity` |
| fireflies | `count`, `y` |
| tea | low table with a cup: `x`, `fill` 0–1 fills, above 1 overflows and spills; `pour` 0/1 shows a stream (a person with `anim: carry`, `stone: "#5b4636"` as the teapot, standing ~85 px left of x, facing right) |
| divider | vertical line: `x`, `y0`, `y1`, `color`, `alpha` (split screens) |
| text | `text`, `y`, `x` (centre, default 540), `box` (hex: coloured pill behind the text), `size`, `color`, `stroke`, `serif`, `alpha`, `counter: {value, fmt: "YEAR {}"}` |

### Recurring patterns
- **Scene 1:** the hook action, plus a gold title `text` at y=250 that fades out.
- **Time passing:** `sky.cycle: 3` + sun/moon `cycle_arc` + a `counter` text.
- **Last scene (moral card):** `sky: card`, stars, moon, dark silhouettes, `captions: false`, serif `text` with the moral at y=640, and the gold line "Mindset Minute  •  New lesson every day" at y=900. Use `lead: 0.6`, `tail: 2.2`.
- Use the same background layers in every scene of a story so the place feels continuous. Change only the colours for time of day and weather.
- Match colour palettes to the mood: warm dawn and golden for hope, cold blue night and storm for danger.

## Names
Use short, clear names that speech-to-text won't mishear (YouTube auto-captions turned "Kamal" into "Camel"). Good: Ravi, Nimal, Maya, Leo, Asha, Tom, Sara. Or use roles: "the old monk", "the young farmer", "a little goat".

## Before committing (required)
1. `python storykit/storykit.py --stills stories/<file>.json prev 0:2 1:3 2:4 ...` and **look at every frame**.
   Check that captions don't collide with the title, people stand on the ground, nothing is cut off, and the scene reads clearly at small size.
2. Optional full render: `python storykit/storykit.py stories/<file>.json out/test.mp4` (~3 min).
3. Commit only the JSON: `git add stories/<file>.json && git commit -m "Story: <title>" && git push`.


## Narrator voice must match the recorded intro/outro

The renderer adds a real recorded intro and outro in the same gender as the story `voice`
(voice/male/ for am_*/bm_*, voice/female/ for af_*/bf_*). Only use a female voice (af_heart, bf_emma)
if voice/female/ contains intro_*.wav files; otherwise always pick a male voice (bm_george, am_michael, bm_lewis)
so every video gets the owner's real voice. When both folders have clips, mix male and female stories across the week.


## Animation extras (automatic unless you turn them off)

- **Camera:** every scene without a `camera` gets a slow push-in or pull-out with a slight pan, so no shot is static.
  Set your own `camera` for a specific move, or `"auto_camera": false` on a scene to keep it still.
  Keep important things (faces, on-screen text) away from the outer 4% of the frame, as the zoom can trim the edges.
- **Dissolves:** scenes blend into each other over 0.4 s. Use `"cut": true` on a scene for a hard cut (a sudden surprise).
- **Floating light specks** drift in every scene without rain/fireflies. `"dust": false` on a scene turns them off.
- **Talking characters (lip-sync):** add `"talk": true` to the person who is saying the narration in that scene,
  e.g. the "I" character in first-person stories, or the master when the narration is his words.
  For only part of a scene use ranges of the scene's length: `"talk": [[0.5, 1.0]]`.
  Their mouth opens and closes with the voice and the head nods slightly. Never give `talk` to two people in the same moment,
  and don't use it while the narrator is describing the scene from outside (third person).
- Characters standing still now breathe, sway their arms and tilt their head a little by themselves.
- **Facial expressions:** every person has eyes, eyebrows, a nose and a mouth that show emotion. Set `"face"` on a person:
  `"calm"` (default), `"happy"`, `"laugh"`, `"sad"`, `"worried"`, `"angry"`, `"surprised"`, `"think"`.
  Change it during a scene with `[[0, "worried"], [0.6, "happy"]]` (times are fractions of the scene).
  `"serene"` = peaceful closed eyes and a soft smile (the default for monks; perfect for Zen masters).
  Without `face`, the pose decides: laugh → laugh, cheer/wave → happy, think → think, others → calm.
- **Monks** wear a saffron robe over one shoulder with prayer beads (`"beads": false` to hide them) and sandals;
  a sitting monk sits on a rock with the robe over his knees. In Zen stories let the master stay `"serene"`
  and give the student the emotions (`"worried"`, `"surprised"`, then `"calm"`).
  Use emotion to tell the story: the poor-mindset character `"worried"`/`"sad"`, the rich-mindset one `"calm"`/`"happy"`,
  the angry moment `"angry"`, the lesson landing `"surprised"` then `"happy"`.
