"""storykit — turns a story JSON into a 1080x1920 animated YouTube Short / Reel / TikTok.

Usage:  python3 storykit.py story.json out.mp4
Style: layered paper-cut silhouettes, gradient skies, burnt-in captions, neural voiceover,
synthesized ambient score. Every scene is described by a list of elements (see README).
"""
import json, math, os, re, subprocess, sys, random, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.environ.get("STORYKIT_MODELS", os.path.join(HERE, "..", "models"))
FONTS = os.environ.get("STORYKIT_FONTS", os.path.join(HERE, "..", "fonts"))
FONT_BOLD = os.path.join(FONTS, "Poppins-Bold.ttf")
FONT_SERIF = os.path.join(FONTS, "Lora-Variable.ttf")

def serif_font(size):
    f = ImageFont.truetype(FONT_SERIF, size)
    try: f.set_variation_by_name("Bold")
    except Exception: pass
    return f

# ---------------------------------------------------------------- helpers
def kf(v, t):
    """Keyframed value: constant, or [[t0,v0],[t1,v1],...] with t in 0..1 (scene-relative)."""
    if isinstance(v, list) and v and isinstance(v[0], list):
        if t <= v[0][0]: return v[0][1]
        for (t0, a), (t1, b) in zip(v, v[1:]):
            if t <= t1:
                u = (t - t0) / max(1e-9, t1 - t0); u = u * u * (3 - 2 * u)  # smoothstep
                if isinstance(a, list): return [x + (y - x) * u for x, y in zip(a, b)]
                return a + (b - a) * u
        return v[-1][1]
    return v

def hexc(c, a=255):
    if isinstance(c, (list, tuple)): return tuple(int(x) for x in c[:3]) + (a,)
    c = c.lstrip("#"); return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), a)

def lerpc(a, b, u): return tuple(int(x + (y - x) * u) for x, y in zip(a, b))

def hi(draw_fn, size, scale=2):
    """Draw at 2x and downsample for anti-aliasing."""
    im = Image.new("RGBA", (size[0] * scale, size[1] * scale), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), scale)
    return im.resize(size, Image.LANCZOS)

SKIES = {  # top, bottom
    "dawn": ("#2b2f5c", "#f6a96b"), "day": ("#3d8fd1", "#bfe3f2"), "golden": ("#5b4a8a", "#ffc46b"),
    "dusk": ("#1f2350", "#e0706a"), "night": ("#05081a", "#1b2450"), "storm": ("#0d1016", "#3a4150"),
    "card": ("#0b0f24", "#2a1f3d"),
}
CYCLE = ["day", "golden", "dusk", "night", "dawn"]

# ---------------------------------------------------------------- element painters
class Scene:
    def __init__(self, spec, dur, rng):
        self.spec, self.dur, self.rng = spec, dur, rng
        self.els = spec["elements"]
        self.ground = spec.get("ground_y", 1450)
        self.static = None
        self.cache = {}

    def phase(self, t):
        c = None
        for e in self.els:
            if e["type"] == "sky" and e.get("cycle"): c = e["cycle"]
        if not c: return None
        p = (t * c) % 1.0 * len(CYCLE)
        i = int(p); return CYCLE[i], CYCLE[(i + 1) % len(CYCLE)], p - i

    def darkness(self, t):
        ph = self.phase(t)
        dk = {"day": 0, "golden": .1, "dusk": .35, "night": .62, "dawn": .25}
        if ph: a, b, u = ph; return dk[a] + (dk[b] - dk[a]) * u
        return 0

    # --- sky
    def sky(self, e, t):
        ph = self.phase(t)
        if ph:
            a, b, u = ph
            top = lerpc(hexc(SKIES[a][0]), hexc(SKIES[b][0]), u); bot = lerpc(hexc(SKIES[a][1]), hexc(SKIES[b][1]), u)
        else:
            p = SKIES.get(e.get("preset", "day")); top, bot = hexc(e.get("top", p[0])), hexc(e.get("bottom", p[1]))
        y = np.linspace(0, 1, H)[:, None] ** 1.2
        col = np.array(top[:3])[None, :] * (1 - y) + np.array(bot[:3])[None, :] * y
        arr = np.repeat(col[:, None, :], W, axis=1).astype(np.uint8)
        return Image.fromarray(arr, "RGB").convert("RGBA")

    def celestial(self, e, t, kind):
        ph = self.phase(t)
        if ph and e.get("cycle_arc"):
            # sun arcs during day/golden/dusk, moon during night/dawn
            c = self.cycle_pos(t, kind)
            if c is None: return None
            x, y = c
        else:
            x, y = kf(e.get("x", 760), t), kf(e.get("y", 900), t)
        r = e.get("r", 110 if kind == "sun" else 80)
        col = hexc(e.get("color", "#ffd98a" if kind == "sun" else "#f1f0e0"))
        key = (kind, r, col)
        if key not in self.cache:
            g = int(r * 3.2); s = 2 * g
            im = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            for i in range(14, 0, -1):
                rr = r + (g - r) * i / 14; a = int(70 * (1 - i / 14) ** 2)
                d.ellipse([g - rr, g - rr, g + rr, g + rr], fill=col[:3] + (a,))
            im = im.filter(ImageFilter.GaussianBlur(r * .35))
            disc = hi(lambda dd, sc: dd.ellipse([(g - r) * sc, (g - r) * sc, (g + r) * sc, (g + r) * sc], fill=col), (s, s))
            im.alpha_composite(disc)
            if kind == "moon":
                sh = hi(lambda dd, sc: dd.ellipse([(g - r + r * .45) * sc, (g - r - r * .2) * sc, (g + r + r * .45) * sc, (g + r - r * .2) * sc], fill=(0, 0, 0, 255)), (s, s))
                a = np.array(im); m = np.array(sh)[..., 3] > 128
                inner = np.zeros(m.shape, bool); yy, xx = np.ogrid[:s, :s]; inner = (xx - g) ** 2 + (yy - g) ** 2 <= r * r
                a[m & inner, 3] = 0; im = Image.fromarray(a)
            self.cache[key] = im
        im = self.cache[key]
        return im, (int(x - im.width / 2), int(y - im.height / 2))

    def cycle_pos(self, t, kind):
        c = [e for e in self.els if e["type"] == "sky"][0]["cycle"]
        p = (t * c) % 1.0  # 0..1 over one full day; sun: 0..0.6, moon: 0.6..1
        if kind == "sun":
            if p > .62: return None
            u = p / .62
        else:
            if p < .55: return None
            u = (p - .55) / .45
        x = 100 + u * 880; y = 1300 - math.sin(u * math.pi) * 950
        return x, y

    def stars(self, e, t):
        if "stars" not in self.cache:
            r = random.Random(7); im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            for _ in range(260):
                x, y = r.uniform(0, W), r.uniform(0, 1250); s = r.choice([1, 1, 1.5, 2, 2.5])
                d.ellipse([x - s, y - s, x + s, y + s], fill=(255, 255, 240, r.randint(120, 255)))
            self.cache["stars"] = im
        a = kf(e.get("alpha", 1), t)
        if self.phase(t): a = max(0, (self.darkness(t) - .3) / .32)
        return self._alpha(self.cache["stars"], a)

    def _alpha(self, im, a):
        if a >= .999: return im
        if a <= .001: return None
        arr = np.array(im); arr[..., 3] = (arr[..., 3] * a).astype(np.uint8); return Image.fromarray(arr)

    def hills(self, e):
        r = random.Random(e.get("seed", 1)); base = e.get("base_y", 1250); amp = e.get("amp", 120)
        ph = [r.uniform(0, 6.28) for _ in range(3)]; fr = [r.uniform(.002, .004), r.uniform(.006, .01), r.uniform(.015, .02)]
        def f(d, s):
            pts = [(0, H * s)]
            for x in range(0, W + 9, 8):
                y = base - amp * (.6 * math.sin(x * fr[0] + ph[0]) + .3 * math.sin(x * fr[1] + ph[1]) + .1 * math.sin(x * fr[2] + ph[2]))
                pts.append((x * s, y * s))
            pts.append((W * s, H * s)); d.polygon(pts, fill=hexc(e.get("color", "#3b4a6b")))
        return hi(f, (W, H))

    def trees(self, e):
        r = random.Random(e.get("seed", 3)); col = hexc(e.get("color", "#1f2b33"))
        def f(d, s):
            for x, y, sc in e.get("items", []):
                h = 220 * sc; tw = 14 * sc
                d.rectangle([(x - tw / 2) * s, (y - h * .45) * s, (x + tw / 2) * s, y * s], fill=col)
                for k in range(4):
                    cx = x + r.uniform(-45, 45) * sc; cy = y - h * .55 - r.uniform(0, 70) * sc; rr = r.uniform(45, 70) * sc
                    d.ellipse([(cx - rr) * s, (cy - rr) * s, (cx + rr) * s, (cy + rr) * s], fill=col)
        return hi(f, (W, H))

    def palms(self, e):
        col = hexc(e.get("color", "#1f2b33"))
        def f(d, s):
            for x, y, sc in e.get("items", []):
                h = 330 * sc; pts = []
                for i in range(11):
                    u = i / 10; pts.append((x + math.sin(u * 1.6) * 40 * sc, y - u * h))
                d.line([(a * s, b * s) for a, b in pts], fill=col, width=int(16 * sc * s))
                tx, ty = pts[-1]
                for ang in range(0, 360, 45):
                    a = math.radians(ang); fl = []
                    for i in range(9):
                        u = i / 8; fl.append((tx + math.cos(a) * 130 * sc * u, ty + math.sin(a) * 50 * sc * u + 70 * sc * u * u))
                    d.line([(p * s, q * s) for p, q in fl], fill=col, width=int(12 * sc * s))
        return hi(f, (W, H))

    def houses(self, e):
        col = hexc(e.get("color", "#2a2633")); win = hexc(e.get("window", "#ffcf7a"))
        def f(d, s):
            for x, y, sc in e.get("items", []):
                w, h = 150 * sc, 100 * sc
                d.rectangle([(x - w / 2) * s, (y - h) * s, (x + w / 2) * s, y * s], fill=col)
                d.polygon([((x - w / 2 - 18 * sc) * s, (y - h) * s), (x * s, (y - h - 75 * sc) * s), ((x + w / 2 + 18 * sc) * s, (y - h) * s)], fill=col)
                if e.get("lit", True):
                    d.rectangle([(x - 22 * sc) * s, (y - 62 * sc) * s, (x + 2 * sc) * s, (y - 38 * sc) * s], fill=win)
        return hi(f, (W, H))

    def ground_img(self, e):
        g = self.ground; col = hexc(e.get("color", "#2d3a2a")); col2 = hexc(e.get("furrow", "#263222"))
        dip = e.get("riverbed")  # [x_end, depth]
        def f(d, s):
            if dip:
                xe, dep = dip; pts = [(0, H * s)]
                for x in range(0, int(xe) + 1, 6):
                    u = x / xe; pts.append((x * s, (g + dep * (1 - u ** 3)) * s))
                pts += [(W * s, g * s), (W * s, H * s)]
            else:
                pts = [(0, H * s), (0, g * s), (W * s, g * s), (W * s, H * s)]
            d.polygon(pts, fill=col)
            if e.get("furrows"):
                x0 = (dip[0] if dip else 0) + 20
                for i in range(1, 9):
                    y = g + i ** 1.6 * 9
                    d.line([(x0 * s, y * s), (W * s, y * s)], fill=col2, width=int((2 + i * .6) * s))
            if e.get("grass", True):
                r = random.Random(4); gc = hexc(e.get("grass_color", "#3e5236"))
                for _ in range(260):
                    x = r.uniform((dip[0] if dip else 0), W); h = r.uniform(10, 26)
                    d.line([(x * s, g * s), ((x + r.uniform(-6, 6)) * s, (g - h) * s)], fill=gc, width=int(3 * s))
        return hi(f, (W, H))

    def build_static(self):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for e in self.els:
            fn = {"hills": self.hills, "trees": self.trees, "palms": self.palms, "houses": self.houses, "ground": self.ground_img}.get(e["type"])
            if fn and not e.get("_front"):
                e["_img"] = fn(e)
        return im

    # --- dynamic
    def water(self, e, t, now):
        level = kf(e["level"], t); x1 = kf(e.get("x1", 300), t)
        col = hexc(e.get("color", "#3d6f8f"), 235); top = hexc(e.get("top", "#9cc6dc"), 255)
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        pts = []; ph = now * 3.0
        rough = kf(e.get("rough", 1), t)
        for x in range(0, int(x1) + 6, 6):
            y = level + rough * (8 * math.sin(x * .03 + ph) + 5 * math.sin(x * .07 - ph * 1.7))
            pts.append((min(x, x1), y))
        d.polygon(pts + [(x1, H), (0, H)], fill=col)
        d.line(pts, fill=top, width=5)
        return im

    def wall_stones(self, e):
        if "_stones" in e: return e["_stones"]
        r = random.Random(e.get("seed", 11)); x0, x1 = e.get("x0", 230), e.get("x1", 420); base = self.ground; top = base - e.get("height", 420)
        stones = []; y = base; row = 0
        while y > top:
            rh = r.uniform(34, 44); x = x0 + (r.uniform(-20, 0) if row % 2 else 0)
            while x < x1:
                w = r.uniform(46, 70); w = min(w, x1 - x) if x1 - x > 28 else w
                stones.append((x, y - rh, x + w, y, r.choice(["#8a8478", "#7a7468", "#958e80", "#6d685e", "#a39b8b"])))
                x += w + 2
            y -= rh + 1; row += 1
        e["_stones"] = stones; return stones

    def wall(self, e, t):
        st = self.wall_stones(e); n = int(round(kf(e.get("fill", 1), t) * len(st)))
        if n <= 0: return None
        if ("wall", n) not in self.cache:
            def f(d, s):
                for (a, b, c, dd, col) in st[:n]:
                    d.rounded_rectangle([a * s, b * s, c * s, dd * s], radius=int(12 * s), fill=hexc(col), outline=hexc("#3b3730"), width=int(3 * s))
                    d.line([((a + 8) * s, (b + 6) * s), ((c - 10) * s, (b + 6) * s)], fill=(255, 255, 255, 45), width=int(3 * s))
            self.cache[("wall", n)] = hi(f, (W, H))
            if len(self.cache) > 60:
                for k in [k for k in self.cache if isinstance(k, tuple) and k[0] == "wall"][:30]: self.cache.pop(k)
        return self.cache[("wall", n)]

    # ------------------------------------------------------------------ characters
    PALETTES = {
        "farmer":     dict(skin="#b07a4f", shirt="#e8dcc4", pants="#3f6e8c", sarong=True,  hair="#2a1d16", hat="straw"),
        "old":        dict(skin="#a8764f", shirt="#efe6d3", pants="#8a6a4a", sarong=True,  hair="#e9e6df", beard=True, staff=True),
        "villager":   dict(skin="#9c6a45", shirt="#d0573f", pants="#2e3b55", sarong=False, hair="#1d1612"),
        "villager_f": dict(skin="#b8835a", shirt="#2f8f83", pants="#2f8f83", dress=True,   hair="#1a1210", bun=True),
        "child":      dict(skin="#c08a5e", shirt="#f2b134", pants="#3b5ba5", sarong=False, hair="#1d1612"),
        "monk":       dict(skin="#b07a4f", shirt="#e07b24", pants="#e07b24", robe=True,    hair=None),
        "student":    dict(skin="#a8724a", shirt="#ffffff", pants="#25324d", sarong=False, hair="#1a1210", bag=True),
    }

    def person(self, e, t, now):
        if e.get("anim") == "carry" and kf(e.get("holding", 1), t) < .5: e = dict(e, anim="idle")
        kind = e.get("kind", "villager"); sc = kf(e.get("s", 1), t); x = kf(e["x"], t); y = kf(e.get("y", self.ground), t)
        anim = e.get("anim", "idle"); face = e.get("facing", 1); ph = e.get("phase", 0)
        pal = dict(self.PALETTES.get(kind, self.PALETTES["villager"])); pal.update({k: v for k, v in e.items() if k in ("skin", "shirt", "pants", "hair", "hat")})
        if e.get("staff"): pal["staff"] = True
        if "shirt" not in e and kind in ("villager", "villager_f", "child", "student"):
            import zlib; v = zlib.crc32(f"{kind}{e.get('phase', 0)}{str(e.get('x'))[:12]}".encode()) % 5
            pal["shirt"] = ["#d0573f", "#3d7ea6", "#8a5cb5", "#e0a030", "#4f9a5a"][v] if kind != "villager_f" else ["#2f8f83", "#c2466b", "#d98e2b", "#5a6fc0", "#8c4f9e"][v]
            if kind == "villager_f": pal["pants"] = pal["shirt"]
        if e.get("silhouette"):
            c = e.get("color", "#141824"); pal.update(skin=c, shirt=c, pants=c, hair=c if pal.get("hair") else None, shade=c)
        H = 360 * sc * (0.66 if kind == "child" else 1.0)
        moving = isinstance(e["x"], list) and abs(kf(e["x"], min(1, t + .01)) - kf(e["x"], t)) > 1e-6
        walking = anim in ("walk", "carry") and moving
        sw = math.sin(now * 7 + ph) if walking else 0.0
        bob = abs(sw) * 5 * sc if walking else (abs(math.sin(now * 9 + ph)) * 9 * sc if anim == "laugh" else math.sin(now * 2 + ph) * 1.5 * sc)
        bend = kf(e.get("bend", 0), t)
        Sw, Sh = int(H * 1.5), int(H * 1.35); ox, oy = Sw / 2, Sh - 6
        def C(hexs, a=255, dk=0.0):
            r, g, b, _ = hexc(hexs); return (int(r * (1 - dk)), int(g * (1 - dk)), int(b * (1 - dk)), a)
        def f(d, s):
            def P(px, py): return ((ox + px * face) * s, (oy + py) * s)
            def limb(pts, col, w):
                q = [P(*p) for p in pts]; d.line(q, fill=col, width=int(w * s), joint="curve")
                for (qx, qy) in (q[0], q[-1]): r = w * s / 2; d.ellipse([qx - r, qy - r, qx + r, qy + r], fill=col)
            def circ(cx, cy, r, col):
                X, Y = P(cx, cy); d.ellipse([X - r * s, Y - r * s, X + r * s, Y + r * s], fill=col)
            lean = bend * H * .07
            hip = (lean * .3, -H * .46 - bob); sho = (lean, -H * .77 - bob + bend * H * .05)
            legw, armw = H * .085, H * .068
            skin, shirt, pants = C(pal["skin"]), C(pal["shirt"]), C(pal["pants"])
            skin_b, shirt_b, pants_b = C(pal["skin"], dk=.18), C(pal["shirt"], dk=.18), C(pal["pants"], dk=.18)
            shoe = C("#2b2420")
            # ---- legs (back then front)
            def leg(k, col):
                if anim == "sit":
                    knee = (hip[0] + H * .2, hip[1] + H * .01); foot = (knee[0] + H * .02, knee[1] + H * .22)
                else:
                    a = k * sw * .5; knee = (hip[0] + math.sin(a) * H * .22, hip[1] + math.cos(a) * H * .22)
                    a2 = a - (abs(sw) * .35 if k * sw < 0 else 0); foot = (knee[0] + math.sin(a2) * H * .22, -2 + 0 * bob)
                limb([hip, knee, foot], col, legw)
                fx, fy = P(foot[0] + H * .03, foot[1]); d.ellipse([fx - H * .065 * s, fy - H * .035 * s, fx + H * .065 * s, fy + H * .012 * s], fill=shoe)
            if not pal.get("robe") and not pal.get("dress"):
                leg(-1, pants_b); leg(1, pants)
            else:
                for k in (-1, 1):
                    a = k * sw * .3; fx_ = hip[0] + math.sin(a) * H * .44
                    X, Y = P(fx_ + H * .03, -2); d.ellipse([X - H * .06 * s, Y - H * .035 * s, X + H * .06 * s, Y + H * .012 * s], fill=shoe)
            # ---- back arm
            def arm(k, col, hand):
                sh = (sho[0] - k * H * .03, sho[1] + H * .035)
                if anim == "carry":
                    el = (sh[0] + H * .1, sh[1] + H * .13); hd = (sh[0] + H * .2, sh[1] + H * .08)
                elif anim == "wave" and k == 1:
                    a = math.sin(now * 8 + ph) * .35; el = (sh[0] + H * .18, sh[1] - H * .02); hd = (el[0] + H * .05 + math.sin(a) * H * .09, el[1] - H * .15)
                elif anim == "laugh" and k == 1:
                    el = (sh[0] + H * .14, sh[1] + H * .04); hd = (el[0] + H * .1, el[1] - H * .12 - bob * .4)   # pointing
                elif anim == "laugh":
                    el = (sh[0] + H * .07, sh[1] + H * .16); hd = (sh[0] + H * .02, sh[1] + H * .26)           # hand on belly
                elif anim == "cheer":
                    jump = abs(math.sin(now * 6 + ph)) * H * .03
                    el = (sh[0] + (H * .1 if k == 1 else -H * .07), sh[1] - H * .1); hd = (sh[0] + (H * .2 if k == 1 else -H * .1), sh[1] - H * .25 - jump)
                elif anim == "think" and k == 1:
                    el = (sh[0] + H * .12, sh[1] + H * .14); hd = (sh[0] + H * .1, sh[1] - H * .02)
                elif pal.get("staff") and k == 1:
                    el = (sh[0] + H * .1, sh[1] + H * .14); hd = (sh[0] + H * .2, sh[1] + H * .2)
                else:
                    a = -k * sw * .45 + .08; el = (sh[0] + math.sin(a) * H * .16, sh[1] + math.cos(a) * H * .16)
                    hd = (el[0] + math.sin(a + .15) * H * .15, el[1] + math.cos(a + .15) * H * .15)
                limb([sh, el, hd], col, armw); circ(hd[0], hd[1], H * .04, hand)
                return hd
            arm(-1, shirt_b, skin_b)
            # ---- body
            tw_s, tw_h = H * .135, H * .11
            if pal.get("robe") or pal.get("dress"):
                hem = H * (.2 if pal.get("robe") else .17)
                d.polygon([P(sho[0] - tw_s, sho[1]), P(sho[0] + tw_s, sho[1]), P(hip[0] + hem, -H * .07), P(hip[0] - hem, -H * .07)], fill=shirt)
                if pal.get("robe"): d.line([P(sho[0] - tw_s * .6, sho[1]), P(hip[0] + tw_s, hip[1] + H * .1)], fill=C(pal["shirt"], dk=.25), width=int(H * .03 * s))
            else:
                x0, y0 = P(sho[0] - tw_s, sho[1]); x1, y1 = P(hip[0] + tw_h, hip[1] + H * .05)
                d.rounded_rectangle([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)], radius=int(H * .06 * s), fill=shirt)
                if pal.get("sarong"):
                    d.polygon([P(hip[0] - tw_h * 1.05, hip[1] + H * .02), P(hip[0] + tw_h * 1.05, hip[1] + H * .02),
                               P(hip[0] + tw_h * 1.25, -H * .14), P(hip[0] - tw_h * 1.25, -H * .14)], fill=pants)
                    d.line([P(hip[0] - tw_h, hip[1] + H * .03), P(hip[0] + tw_h, hip[1] + H * .03)], fill=C(pal["pants"], dk=.3), width=int(H * .02 * s))
                if pal.get("bag"):
                    d.rounded_rectangle([*P(sho[0] - tw_s * 1.5, sho[1] + H * .03), *P(sho[0] - tw_s * .7, hip[1])] if face > 0 else
                                        [*P(sho[0] - tw_s * .7, sho[1] + H * .03), *P(sho[0] - tw_s * 1.5, hip[1])], radius=int(H * .03 * s), fill=C("#c2463b"))
            # neck + head
            hr = H * (.115 if kind == "child" else .1)
            hc = (sho[0] + H * .015 + (H * .02 if anim == "laugh" else 0), sho[1] - hr * 1.05 - (math.sin(now * 9) * 2 * sc if anim == "laugh" else 0))
            limb([(sho[0], sho[1]), (hc[0], hc[1] + hr * .6)], skin, H * .05)
            circ(hc[0], hc[1], hr, skin)
            hair = pal.get("hair")
            if hair and kind != "old":
                X, Y = P(hc[0], hc[1]); R = hr * s * 1.04
                d.pieslice([X - R, Y - R, X + R, Y + R], 180, 360, fill=C(hair))
                bx = hc[0] - hr * .55; circ(bx, hc[1] - hr * .1, hr * .5, C(hair))                         # back of head
                if pal.get("bun"): circ(hc[0] - hr * .95, hc[1] - hr * .45, hr * .42, C(hair))
            if kind == "old":
                X, Y = P(hc[0], hc[1]); R = hr * s * 1.02
                a0, a1 = (115, 235) if face > 0 else (-55, 65)
                d.arc([X - R, Y - R, X + R, Y + R], a0, a1, fill=C(pal["hair"]), width=int(hr * .42 * s))
                d.pieslice([*P(hc[0] - hr * .2, hc[1] + hr * .1), *P(hc[0] + hr * .9, hc[1] + hr * 1.1)] if face > 0 else
                           [*P(hc[0] + hr * .9, hc[1] + hr * .1), *P(hc[0] - hr * .2, hc[1] + hr * 1.1)], 0, 180, fill=C(pal["hair"]))   # beard
            # face (side 3/4 view)
            blink = (now * 1.0 + ph) % 3.4 < .12
            ex, ey = hc[0] + hr * .45, hc[1] + hr * .14
            if blink: d.line([P(ex - hr * .12, ey), P(ex + hr * .12, ey)], fill=C("#1b1410"), width=max(2, int(H * .012 * s)))
            else: circ(ex, ey, hr * .11, C("#1b1410"))
            circ(ex - hr * .55, ey, hr * .1, C("#1b1410"))
            mx, my = hc[0] + hr * .45, hc[1] + hr * .58
            if anim in ("laugh", "cheer", "wave"):
                X, Y = P(mx - hr * .25, my - hr * .15); X2, Y2 = P(mx + hr * .25, my + hr * .2)
                d.pieslice([min(X, X2), Y, max(X, X2), Y2], 0, 180, fill=C("#5a1e1a"))
            else:
                X, Y = P(mx - hr * .2, my - hr * .12); X2, Y2 = P(mx + hr * .2, my + hr * .1)
                d.arc([min(X, X2), Y, max(X, X2), Y2], 20, 160, fill=C("#5a2a20"), width=max(2, int(H * .012 * s)))
            sk = hexc(pal["skin"]); ck = tuple(int(a * .7 + b * .3) for a, b in zip(sk[:3], (230, 120, 110))) + (255,)
            if not e.get("silhouette"): circ(hc[0] + hr * .12, hc[1] + hr * .42, hr * .12, ck)            # cheek
            if pal.get("hat") == "straw":
                d.polygon([P(hc[0] - hr * 2.3, hc[1] - hr * .45), P(hc[0] + hr * .1, hc[1] - hr * 1.95), P(hc[0] + hr * 2.4, hc[1] - hr * .45)], fill=C("#d9b26a"))
                d.line([P(hc[0] - hr * 1.6, hc[1] - hr * .75), P(hc[0] + hr * 1.7, hc[1] - hr * .75)], fill=C("#a8823f"), width=int(H * .014 * s))
            # ---- front arm + props
            hd = arm(1, shirt, skin)
            if anim == "carry":
                circ(hd[0] + H * .03, hd[1] - H * .05, H * .085, C(e.get("stone", "#8f897c"))); circ(hd[0] + H * .01, hd[1] - H * .08, H * .025, C("#b9b3a6"))
            if pal.get("staff"):
                d.line([P(hd[0] + H * .01, hd[1] - H * .16), P(hd[0] + H * .03, -2)], fill=C("#6b4a2b"), width=int(H * .025 * s))
        im = hi(f, (Sw, Sh))
        return im, (int(x - ox), int(y - oy))

    def clouds(self, e, t, now):
        if "_cl" not in e:
            r = random.Random(e.get("seed", 5)); cl = []
            for i in range(e.get("count", 4)):
                w = r.uniform(260, 460); h = w * .32
                def f(d, s, w=w, h=h, r=r):
                    for k in range(6):
                        cx = r.uniform(w * .2, w * .8); cy = r.uniform(h * .45, h * .75); rr = r.uniform(h * .3, h * .55)
                        d.ellipse([(cx - rr) * s, (cy - rr) * s, (cx + rr) * s, (cy + rr) * s], fill=hexc(e.get("color", "#ffffff")))
                    d.rounded_rectangle([w * .1 * s, h * .55 * s, w * .9 * s, h * s], radius=int(h * .2 * s), fill=hexc(e.get("color", "#ffffff")))
                cl.append((hi(f, (int(w), int(h))), r.uniform(-200, W), r.uniform(*e.get("y", [150, 700])), r.uniform(8, 22) * e.get("speed", 1)))
            e["_cl"] = cl
        a = kf(e.get("alpha", .8), t); out = []
        for im, x, y, v in e["_cl"]:
            xx = (x + v * now) % (W + 600) - 400
            out.append((self._alpha(im, a), (int(xx), int(y))))
        return out

    def rain(self, e, t, now, d):
        n = int(e.get("count", 380) * kf(e.get("intensity", 1), t)); r = random.Random(9)
        for i in range(n):
            x0, y0, v = r.uniform(0, W + 400), r.uniform(0, H), r.uniform(1600, 2400)
            y = (y0 + v * now) % (H + 100) - 50; x = (x0 - v * .25 * now) % (W + 400) - 200
            d.line([(x, y), (x - 10, y + 42)], fill=(190, 205, 230, r.randint(70, 140)), width=2)

    def birds(self, e, t, now, d):
        r = random.Random(13); col = hexc(e.get("color", "#1a1d2a"))
        for i in range(e.get("count", 5)):
            x = (r.uniform(-300, 0) + now * r.uniform(70, 110)) % (W + 300) - 100; y = r.uniform(*e.get("y", [350, 700])) + math.sin(now + i) * 10
            f = math.sin(now * 8 + i) * 9
            d.line([(x - 16, y - f), (x, y), (x + 16, y - f)], fill=col, width=4, joint="curve")

    def fireflies(self, e, t, now, d):
        r = random.Random(17)
        for i in range(e.get("count", 25)):
            x = r.uniform(0, W) + math.sin(now * .7 + i) * 30; y = r.uniform(*e.get("y", [1200, 1500])) + math.cos(now * .9 + i * 2) * 20
            a = int(200 * (.5 + .5 * math.sin(now * 3 + i * 1.7)))
            d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(255, 230, 140, a))

    def splash(self, e, t, now, d):
        inten = kf(e.get("intensity", 1), t)
        if inten <= .02: return
        r = random.Random(21); x0 = kf(e.get("x", 230), t); y0 = kf(e.get("y", 1100), t)
        for i in range(int(60 * inten)):
            ph = (now * r.uniform(1.2, 2) + r.random()) % 1
            vx = -r.uniform(80, 260); vy = -r.uniform(250, 600)
            x = x0 + vx * ph; y = y0 + vy * ph + 900 * ph * ph; s = r.uniform(4, 9) * (1 - ph)
            d.ellipse([x - s, y - s, x + s, y + s], fill=(200, 225, 240, int(220 * (1 - ph))))

    def bolt(self, e, now, d):
        for tt in e.get("times", []):
            dt = now - tt
            if 0 <= dt < .18:
                r = random.Random(int(tt * 100)); x = r.uniform(150, 900); y = 0; pts = [(x, y)]
                while y < 1150: y += r.uniform(40, 90); x += r.uniform(-60, 60); pts.append((x, y))
                d.line(pts, fill=(235, 240, 255, 255), width=7); d.line(pts, fill=(255, 255, 255, 255), width=3)

    def flash(self, e, now):
        f = 0
        for tt in e.get("times", []):
            dt = now - tt
            if 0 <= dt < .35: f = max(f, (1 - dt / .35) * .55)
        return f

    def text_el(self, e, t):
        a = kf(e.get("alpha", 1), t)
        if a <= .01: return None
        if "counter" in e:
            c = e["counter"]; e = dict(e, text=c["fmt"].format(int(round(kf(c["value"], t)))))
        key = ("txt", e["text"], e.get("size", 70))
        if key not in self.cache:
            font = serif_font(e.get("size", 70)) if e.get("serif") else ImageFont.truetype(FONT_BOLD, e.get("size", 70))
            lines = wrap(e["text"], font, e.get("width", 900))
            lh = int(e.get("size", 70) * 1.3); im = Image.new("RGBA", (W, lh * len(lines) + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            for i, ln in enumerate(lines):
                d.text((W / 2, 20 + i * lh + lh / 2), ln, font=font, anchor="mm", fill=hexc(e.get("color", "#ffffff")),
                       stroke_width=e.get("stroke", 0), stroke_fill=(10, 10, 20, 255))
            self.cache[key] = im
        im = self.cache[key]
        return self._alpha(im, a), (0, int(kf(e.get("y", 300), t) - im.height / 2))

    # --- frame
    def frame(self, now):
        t = now / self.dur
        if self.static is None: self.build_static(); self.static = True
        img = None; overlay_draw_fns = []
        for e in self.els:
            ty = e["type"]
            if ty == "sky": img = self.sky(e, t); continue
            if img is None: img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
            res = None
            if "show" in e and not (e["show"][0] <= t < e["show"][1]): continue
            if "_img" in e: res = (e["_img"], (0, 0))
            elif ty == "stars": s = self.stars(e, t); res = (s, (0, 0)) if s else None
            elif ty in ("sun", "moon"): res = self.celestial(e, t, ty)
            elif ty == "clouds":
                for im, p in self.clouds(e, t, now):
                    if im: img.alpha_composite(im, dest=(max(p[0], -10**6), p[1])) if p[0] >= 0 else paste_clip(img, im, p)
                continue
            elif ty == "water": res = (self.water(e, t, now), (0, 0))
            elif ty == "wall": w = self.wall(e, t); res = (w, (0, 0)) if w else None
            elif ty == "person": res = self.person(e, t, now)
            elif ty == "text": res = self.text_el(e, t)
            elif ty in ("rain", "birds", "fireflies", "splash", "lightning"):
                lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
                if ty == "lightning": self.bolt(e, now, d)
                else: getattr(self, ty)(e, t, now, d)
                res = (lay, (0, 0))
            if res and res[0] is not None: paste_clip(img, res[0], res[1])
        # global grading
        arr = np.asarray(img.convert("RGB")).astype(np.float32)
        dk = self.darkness(t) + kf(self.spec.get("dark", 0), t)
        if dk > 0: arr = arr * (1 - dk * np.array([.75, .7, .45]))
        for e in self.els:
            if e["type"] == "lightning":
                fl = self.flash(e, now); arr = arr + (255 - arr) * fl
        fade = kf(self.spec.get("fade", 1), t)
        arr = vignette(arr) * fade
        out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        cam = self.spec.get("camera", {})
        z = kf(cam.get("zoom", 1.0), t); cx = kf(cam.get("cx", W / 2), t); cy = kf(cam.get("cy", H / 2), t)
        if abs(z - 1) > 1e-3:
            cw, ch = W / z, H / z; x0 = min(max(cx - cw / 2, 0), W - cw); y0 = min(max(cy - ch / 2, 0), H - ch)
            out = out.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
        return out

def paste_clip(base, im, pos):
    x, y = pos; bx0, by0 = max(0, x), max(0, y); bx1, by1 = min(base.width, x + im.width), min(base.height, y + im.height)
    if bx1 <= bx0 or by1 <= by0: return
    crop = im.crop((bx0 - x, by0 - y, bx1 - x, by1 - y)); base.alpha_composite(crop, dest=(bx0, by0))

_VIG = None
def vignette(arr):
    global _VIG
    if _VIG is None:
        yy, xx = np.mgrid[0:H, 0:W]; d = ((xx - W / 2) / (W * .75)) ** 2 + ((yy - H / 2) / (H * .7)) ** 2
        _VIG = (1 - np.clip(d - .25, 0, 1) * .45)[..., None].astype(np.float32)
    return arr * _VIG

def wrap(text, font, width):
    words = text.split(); lines = []; cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if font.getlength(trial) <= width: cur = trial
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

# ---------------------------------------------------------------- watermark
def make_watermark(text):
    """Small semi-transparent channel mark, top-right (clear of TikTok/Shorts UI and captions)."""
    if not text: return None
    font = ImageFont.truetype(FONT_BOLD, 30); tw = font.getlength(text)
    im = Image.new("RGBA", (int(tw) + 70, 56), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, im.width - 1, 55], radius=28, fill=(10, 12, 30, 110))
    d.ellipse([16, 15, 42, 41], fill=(255, 214, 140, 235))          # little moon
    d.ellipse([25, 11, 51, 37], fill=(10, 12, 30, 0))
    d.text((54, 28), text, font=font, anchor="lm", fill=(255, 243, 214, 215))
    a = np.array(im); a[..., 3] = (a[..., 3] * 0.85).astype(np.uint8)
    return Image.fromarray(a)

# ---------------------------------------------------------------- captions
class Captions:
    def __init__(self): self.font = ImageFont.truetype(FONT_BOLD, 82); self.cache = {}
    def img(self, text, hl):
        if text in self.cache: return self.cache[text]
        lines = wrap(text, self.font, 880); lh = 108
        im = Image.new("RGBA", (W, lh * len(lines) + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for i, ln in enumerate(lines):
            # draw word by word to colour highlight words
            total = self.font.getlength(ln); x = (W - total) / 2; y = 20 + i * lh
            for wd in ln.split(" "):
                c = (255, 214, 92, 255) if re.sub(r"\W", "", wd.lower()) in hl else (255, 255, 255, 255)
                d.text((x, y), wd, font=self.font, fill=c, stroke_width=9, stroke_fill=(12, 12, 20, 255))
                x += self.font.getlength(wd + " ")
        self.cache[text] = im; return im
    def draw(self, frame, chunks, now, y, hl):
        for c in chunks:
            if c["start"] <= now < c["end"]:
                im = self.img(c["text"], hl); age = now - c["start"]
                s = .86 + .14 * min(1, age / .12) ** .5 if age < .12 else 1.0
                if s < .999:
                    im = im.resize((int(im.width * s), int(im.height * s)), Image.BILINEAR)
                paste_clip(frame, im, (int((W - im.width) / 2), int(y - im.height / 2)))

def chunk_sentence(sent, maxw=4):
    words = sent.split(); out = []; cur = []
    for w in words:
        cur.append(w)
        if len(cur) >= maxw or re.search(r"[,.!?…;:]$", w) and len(cur) >= 2: out.append(" ".join(cur)); cur = []
    if cur:
        if out and len(cur) == 1: out[-1] += " " + cur[0]
        else: out.append(" ".join(cur))
    return out

# ---------------------------------------------------------------- audio
def tts_scenes(story, workdir):
    from kokoro_onnx import Kokoro
    k = Kokoro(os.path.join(MODELS, "kokoro.onnx"), os.path.join(MODELS, "voices.bin"))
    voice = story.get("voice", "bm_george"); speed = story.get("speed", 0.95); sr = 24000
    out = []
    for sc in story["scenes"]:
        sents = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", sc["narration"].strip()) if s.strip()]
        lead = sc.get("lead", .35); pieces = [np.zeros(int(lead * sr), np.float32)]; tcur = lead; chunks = []
        for s in sents:
            spoken = s.replace("…", ",").replace("'", "’") if False else s.replace("…", "...")
            a, sr = k.create(spoken, voice=voice, speed=speed, lang="en-us")
            a = trim(a.astype(np.float32), sr); dur = len(a) / sr
            parts = chunk_sentence(s); tot = sum(len(p) for p in parts); tt = tcur
            for p in parts:
                d = dur * len(p) / tot; chunks.append({"text": p, "start": tt, "end": tt + d}); tt += d
            pieces += [a, np.zeros(int(sc.get("gap", .28) * sr), np.float32)]; tcur += dur + sc.get("gap", .28)
        tail = sc.get("tail", .45); pieces.append(np.zeros(int(tail * sr), np.float32)); tcur += tail
        if chunks: chunks[-1]["end"] = tcur - .05
        voice_audio = np.concatenate(pieces); dur = max(len(voice_audio) / sr, sc.get("min_dur", 0))
        out.append({"audio": voice_audio, "dur": dur, "chunks": chunks})
    return out, sr

def trim(a, sr, th=.01):
    idx = np.where(np.abs(a) > th)[0]
    if not len(idx): return a
    return a[max(0, idx[0] - int(.03 * sr)): idx[-1] + int(.08 * sr)]

def music(total, sr, mood="warm", seed=0):
    t = np.arange(int(total * sr)) / sr
    prog = {"warm": [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]],
            "sad": [[57, 60, 64], [52, 55, 59], [53, 57, 60], [50, 53, 57]],
            "hopeful": [[48, 52, 55], [55, 59, 62], [57, 60, 64], [53, 57, 60]]}[mood]
    seg = 4.0; out = np.zeros_like(t)
    for i in range(int(total / seg) + 1):
        ch = prog[i % len(prog)]; t0 = i * seg; m = (t >= t0) & (t < t0 + seg + 1.5)
        tt = t[m] - t0; env = np.minimum(1, tt / 1.2) * np.exp(-np.maximum(0, tt - seg) * 2.5)
        for n in ch + [ch[0] - 12]:
            f = 440 * 2 ** ((n - 69) / 12)
            out[m] += env * (np.sin(2 * np.pi * f * tt) + .3 * np.sin(4 * np.pi * f * tt + .5) + .1 * np.sin(6 * np.pi * f * tt)) * (.6 if n < 50 else .25)
        # soft pluck arpeggio
        for j, n in enumerate(ch * 2):
            tp = t0 + j * seg / 6; mm = (t >= tp) & (t < tp + 1.5); tt2 = t[mm] - tp
            f = 440 * 2 ** ((n + 12 - 69) / 12); out[mm] += .18 * np.exp(-tt2 * 3.5) * np.sin(2 * np.pi * f * tt2)
    out /= np.max(np.abs(out)) + 1e-9
    return out * .16

def rain_noise(n, sr, seed=1):
    r = np.random.default_rng(seed); x = r.standard_normal(n).astype(np.float32)
    k = np.ones(6) / 6; x = np.convolve(x, k, "same"); return x / (np.max(np.abs(x)) + 1e-9)

def thunder(sr, seed=2):
    r = np.random.default_rng(seed); n = int(3 * sr); x = r.standard_normal(n)
    x = np.convolve(x, np.ones(120) / 120, "same"); env = np.exp(-np.arange(n) / sr * 1.4) * np.minimum(1, np.arange(n) / (.08 * sr))
    x = x * env; return (x / (np.max(np.abs(x)) + 1e-9)).astype(np.float32)

# ---------------------------------------------------------------- render
def render(story_path, out_path):
    story = json.load(open(story_path)); work = os.path.splitext(out_path)[0] + "_work"; os.makedirs(work, exist_ok=True)
    voice, sr = tts_scenes(story, work)
    hl = set(w.lower() for w in story.get("highlight", []))
    caps = Captions(); files = []
    wm = make_watermark(story.get("watermark", "Tiny Tales Daily"))
    for i, (sc, vo) in enumerate(zip(story["scenes"], voice)):
        dur = vo["dur"]; nfr = int(round(dur * FPS)); vo["nfr"] = nfr
        scene = Scene(sc, dur, random.Random(i))
        tmp = os.path.join(work, f"s{i:02d}.tmp.mp4"); fin = os.path.join(work, f"s{i:02d}.mp4")
        p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                              "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS), tmp], stdin=subprocess.PIPE)
        for f in range(nfr):
            now = f / FPS; fr = scene.frame(now).convert("RGBA")
            if sc.get("captions", True): caps.draw(fr, vo["chunks"], now, sc.get("caption_y", 700), hl)
            if wm is not None and sc.get("watermark", True): fr.alpha_composite(wm, dest=(W - wm.width - 36, 330))
            p.stdin.write(fr.convert("RGB").tobytes())
        p.stdin.close()
        if p.wait() != 0: raise SystemExit(f"ffmpeg failed on scene {i}")
        os.replace(tmp, fin); files.append(fin); print(f"scene {i} done ({dur:.1f}s)", flush=True)
    # audio mix
    total = sum(v["nfr"] for v in voice) / FPS; N = int(total * sr) + sr
    vo_track = np.zeros(N, np.float32); fx = np.zeros(N, np.float32); off = 0.0
    for sc, v in zip(story["scenes"], voice):
        s = int(off * sr); a = v["audio"][: int(v["nfr"] / FPS * sr)]; vo_track[s:s + len(a)] += a
        if sc.get("sfx_rain"):
            n = int(v["nfr"] / FPS * sr); fx[s:s + n] += rain_noise(n, sr) * .07 * sc["sfx_rain"]
        for e in sc["elements"]:
            if e["type"] == "lightning":
                for tt in e.get("times", []):
                    th = thunder(sr); ss = s + int((tt + .25) * sr); fx[ss:ss + len(th)] += th[: max(0, N - ss)] * .5
        off += v["nfr"] / FPS
    mus = music(total + 1, sr, story.get("mood", "warm"))[:N]
    mus = np.pad(mus, (0, N - len(mus)))
    # duck music under voice
    env = np.convolve(np.abs(vo_track), np.ones(int(.25 * sr)) / (.25 * sr), "same"); duck = 1 - np.clip(env * 6, 0, .55)
    mix = vo_track * .95 + mus * duck + fx
    fade = np.ones(N); fl = int(1.2 * sr); fade[-fl:] = np.linspace(1, 0, fl); mix = mix * fade
    mix = mix / max(1, np.max(np.abs(mix)) / .95)
    import soundfile as sf
    wav = os.path.join(work, "mix.wav"); sf.write(wav, mix[: int(total * sr)], sr)
    lst = os.path.join(work, "list.txt"); open(lst, "w").write("".join(f"file '{os.path.abspath(f)}'\n" for f in files))
    vid = os.path.join(work, "video.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", vid], check=True)
    tmp = out_path + ".tmp.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", vid, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, out_path); print(f"done: {out_path} ({total:.1f}s)")

def stills(story_path, outdir, times):
    """Preview: render single frames. times = list of (scene_index, t_seconds)."""
    story = json.load(open(story_path)); os.makedirs(outdir, exist_ok=True)
    for si, ts in times:
        si = int(si); sc = story["scenes"][si]; scene = Scene(sc, sc.get("preview_dur", 8), random.Random(si))
        fr = scene.frame(ts).convert("RGBA")
        wm = make_watermark(story.get("watermark", "Tiny Tales Daily"))
        if wm is not None and sc.get("watermark", True): fr.alpha_composite(wm, dest=(W - wm.width - 36, 330))
        if sc.get("captions", True): Captions().draw(fr, [{"text": "Sample caption text here", "start": 0, "end": 99}], 1, sc.get("caption_y", 700), set(story.get("highlight", [])))
        fr.convert("RGB").save(os.path.join(outdir, f"p{si}_{ts}.jpg"), quality=88)

if __name__ == "__main__":
    if sys.argv[1] == "--stills":
        stills(sys.argv[2], sys.argv[3], [tuple(map(float, x.split(":"))) for x in sys.argv[4:]])
    else:
        render(sys.argv[1], sys.argv[2])
