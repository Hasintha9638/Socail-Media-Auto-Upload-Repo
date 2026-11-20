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
    def __init__(self, spec, dur, rng, idx=0, talk=None):
        self.spec, self.dur, self.rng, self.idx = spec, dur, rng, idx
        self.talk = talk            # per-frame voice loudness 0..1 (drives the speaking character's mouth)
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
        "monk":       dict(skin="#b07a4f", shirt="#e8862a", pants="#e8862a", robe=True,    hair=None),
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
        speaker = e.get("talk", False)   # true = this character says the narration; [[t0, t1], ...] = only in those parts of the scene (0..1)
        if isinstance(speaker, list): speaker = any(r[0] <= t < r[1] for r in speaker)
        talk = 0.0
        if speaker and self.talk is not None and anim not in ("laugh", "cheer"):
            talk = float(self.talk[min(len(self.talk) - 1, int(now * FPS))])
        nod = math.sin(now * 5.3 + ph) * talk * 3 * sc + (math.sin(now * .9 + ph) * 1.2 * sc if not walking else 0)
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
            shoe = C("#7a5534") if pal.get("robe") else C("#2b2420")   # monks wear sandals
            def L(hexs, k):   # lighter shade (opaque, so nothing punches a hole in the layer)
                r_, g_, b_, _ = hexc(hexs); return (int(r_ + (255 - r_) * k), int(g_ + (255 - g_) * k), int(b_ + (255 - b_) * k), 255)
            # ---- legs (back then front)
            def leg(k, col):
                if anim == "sit":
                    knee = (hip[0] + H * .2, hip[1] + H * .01); foot = (knee[0] + H * .02, knee[1] + H * .22)
                else:
                    a = k * sw * .5; knee = (hip[0] + math.sin(a) * H * .22, hip[1] + math.cos(a) * H * .22)
                    a2 = a - (abs(sw) * .35 if k * sw < 0 else 0); foot = (knee[0] + math.sin(a2) * H * .22, -2 + 0 * bob)
                if kind == "child" and not e.get("silhouette"):   # shorts
                    limb([knee, foot], skin_b if k < 0 else skin, legw * .82); limb([hip, knee], col, legw * 1.12)
                else:
                    limb([hip, knee, foot], col, legw)
                fx, fy = P(foot[0] + H * .03, foot[1]); d.ellipse([fx - H * .065 * s, fy - H * .035 * s, fx + H * .065 * s, fy + H * .012 * s], fill=shoe)
            if anim == "sit" and not e.get("no_seat"):   # something to sit on, so nobody floats
                rk = C(e.get("seat", "#7d7468")) if not e.get("silhouette") else C(pal["shirt"])
                X0, Y0 = P(hip[0] - H * .2, hip[1] + H * .02); X1, Y1 = P(hip[0] + H * .14, 6)
                d.rounded_rectangle([min(X0, X1), Y0, max(X0, X1), Y1], radius=int(H * .07 * s), fill=rk)
                X0, Y0 = P(hip[0] - H * .17, hip[1] + H * .04); X1, Y1 = P(hip[0] + H * .02, hip[1] + H * .08)
                d.rounded_rectangle([min(X0, X1), Y0, max(X0, X1), Y1], radius=int(H * .02 * s), fill=C(e.get("seat", "#7d7468"), dk=-.15) if not e.get("silhouette") else rk)
            if not pal.get("robe") and not pal.get("dress"):
                leg(-1, pants_b); leg(1, pants)
            elif not (pal.get("robe") and anim == "sit" and not e.get("silhouette")):
                for k in (-1, 1):
                    a = k * sw * .3; fx_ = hip[0] + math.sin(a) * H * .44
                    if pal.get("dress") and not e.get("silhouette"):
                        limb([(hip[0] + k * H * .035, -H * .2), (fx_ + H * .01, -H * .03)], skin_b if k < 0 else skin, H * .05)
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
                    if k == 1: el = (sh[0] + H * .17, sh[1] - H * .015); hd = (el[0] + H * .07, el[1] - H * .2 - jump)   # out to the side, then up (clear of the face)
                    else: el = (sh[0] - H * .09, sh[1] - H * .08); hd = (sh[0] - H * .12, sh[1] - H * .25 - jump)
                elif anim == "think" and k == 1:
                    el = (sh[0] + H * .12, sh[1] + H * .14); hd = (sh[0] + H * .1, sh[1] - H * .02)
                elif pal.get("staff") and k == 1:
                    el = (sh[0] + H * .1, sh[1] + H * .14); hd = (sh[0] + H * .2, sh[1] + H * .2)
                else:
                    a = -k * sw * .45 + .08 + (0 if walking else math.sin(now * 1.5 + ph + k) * .05)   # relaxed sway when standing
                    el = (sh[0] + math.sin(a) * H * .16, sh[1] + math.cos(a) * H * .16)
                    hd = (el[0] + math.sin(a + .15) * H * .15, el[1] + math.cos(a + .15) * H * .15)
                if kind in ("villager", "farmer", "child", "villager_f") and not e.get("silhouette") and col not in (skin, skin_b):
                    mid = (sh[0] + (el[0] - sh[0]) * .6, sh[1] + (el[1] - sh[1]) * .6)
                    limb([sh, el, hd], hand, armw * .9)                                   # bare arm
                    if kind == "villager_f": circ(sh[0], sh[1] + H * .01, armw * .95, col)  # puff sleeve
                    limb([sh, mid], col, armw * 1.3)                                      # sleeve
                else:
                    limb([sh, el, hd], col, armw)
                draw_hand(hd, el, hand, k)
                return hd
            def draw_hand(hd, el, col, k):
                """Small cartoon hand: palm, thumb and four fingers pointing along the forearm (a fist when holding something)."""
                if e.get("silhouette"): circ(hd[0], hd[1], H * .04, col); return
                vx, vy = hd[0] - el[0], hd[1] - el[1]; n = math.hypot(vx, vy) or 1; vx, vy = vx / n, vy / n; px, py = -vy, vx
                line_c = C(pal["skin"], dk=.28) if col == skin else C(pal["skin"], dk=.4)
                holding = anim == "carry" or (pal.get("staff") and k == 1 and anim not in ("think", "wave", "cheer", "laugh", "sit"))
                spread = anim in ("wave", "cheer") and k == 1
                pr = H * .036
                circ(hd[0], hd[1], pr, col)                                                       # palm
                tb = (hd[0] + px * pr * .85 - vx * pr * .2, hd[1] + py * pr * .85 - vy * pr * .2)  # thumb
                limb([tb, (tb[0] + (px * .5 + vx * .6) * pr * .8, tb[1] + (py * .5 + vy * .6) * pr * .8)], col, H * .017)
                if holding:                                                                       # fist: knuckle bumps
                    for i in range(4):
                        o = (i - 1.5) * .42
                        circ(hd[0] + vx * pr * .7 + px * o * pr, hd[1] + vy * pr * .7 + py * o * pr, pr * .3, col)
                    return
                for i in range(4):
                    o = (i - 1.6) * (.5 if spread else .36); ln = pr * (1.05 if i in (1, 2) else .85) * (1.1 if spread else 1)
                    bx, by = hd[0] + vx * pr * .55 + px * o * pr, hd[1] + vy * pr * .55 + py * o * pr
                    dx, dy = vx + px * o * (.35 if spread else .12), vy + py * o * (.35 if spread else .12)
                    limb([(bx, by), (bx + dx * ln, by + dy * ln)], col, H * .015)
                for i in range(3):                                                                # gaps between fingers
                    o = (i - 1.05) * (.5 if spread else .36)
                    bx, by = hd[0] + vx * pr * .75 + px * o * pr, hd[1] + vy * pr * .75 + py * o * pr
                    X0, Y0 = P(bx, by); X1, Y1 = P(bx + vx * pr * .45, by + vy * pr * .45)
                    d.line([(X0, Y0), (X1, Y1)], fill=line_c, width=max(1, int(H * .004 * s)))
            arm(-1, shirt_b, skin_b)
            # ---- body
            tw_s, tw_h = H * .135, H * .11
            if pal.get("robe") and not e.get("silhouette"):
                # Theravada-style robe: saffron over one shoulder, darker under-robe at the hem, soft folds, prayer beads
                robe_d = C(pal["shirt"], dk=.2); robe_l = L(pal["shirt"], .2); under = C("#8a3a1c")
                sway = math.sin(now * 1.3 + ph) * H * .006 + sw * H * .012
                sitting = anim == "sit"
                if sitting:   # lap + hanging legs wrapped in the robe
                    hem = H * .15; bot = hip[1] + H * .08
                    knee_x = hip[0] + H * .24
                    d.polygon([P(hip[0] - H * .12, hip[1] - H * .03), P(knee_x + H * .05, hip[1] - H * .01), P(knee_x + H * .07, hip[1] + H * .1), P(hip[0] - H * .14, hip[1] + H * .1)], fill=robe_d)
                    d.polygon([P(knee_x - H * .05, hip[1] + H * .05), P(knee_x + H * .07, hip[1] + H * .05), P(knee_x + H * .09, -H * .09), P(knee_x - H * .07, -H * .09)], fill=shirt)
                    d.polygon([P(knee_x - H * .075, -H * .1), P(knee_x + H * .095, -H * .1), P(knee_x + H * .1, -H * .02), P(knee_x - H * .08, -H * .02)], fill=under)
                    for k_ in (-1, 1):
                        X, Y = P(knee_x + k_ * H * .03, -2); d.ellipse([X - H * .045 * s, Y - H * .03 * s, X + H * .045 * s, Y + H * .01 * s], fill=shoe)
                else:
                    hem = H * .19; bot = -H * .1
                    d.polygon([P(hip[0] - hem * 1.03 + sway, -H * .13), P(hip[0] + hem * 1.03 + sway, -H * .13),
                               P(hip[0] + hem * 1.05 + sway, -H * .02), P(hip[0] - hem * 1.05 + sway, -H * .02)], fill=under)   # reaches the sandals
                tw = tw_s * .92
                d.polygon([P(sho[0] - tw, sho[1] + H * .03), P(sho[0] - tw * .55, sho[1] - H * .012), P(sho[0] + tw * .6, sho[1] - H * .012), P(sho[0] + tw, sho[1] + H * .03),
                           P(hip[0] + hem * .98 + sway, bot), P(hip[0] + sway * .5, bot + H * .012), P(hip[0] - hem + sway, bot)], fill=shirt)
                circ(sho[0] - tw * .62, sho[1] + H * .035, H * .05, shirt)                                                                    # rounded back shoulder
                d.polygon([P(sho[0] + tw * .05, sho[1] - H * .008), P(sho[0] + tw * .7, sho[1] - H * .01), P(sho[0] + tw * 1.05, sho[1] + H * .04), P(sho[0] + tw * .98, sho[1] + H * .1)], fill=skin)   # bare shoulder
                d.line([P(sho[0] + tw * .05, sho[1]), P(sho[0] + tw * .98, sho[1] + H * .1)], fill=robe_l, width=max(2, int(H * .012 * s)))          # robe edge
                d.line([P(sho[0] - tw * .75, sho[1] + H * .03), P(hip[0] + tw * .2, hip[1] + H * .01), P(hip[0] + hem * .7 + sway, bot - H * .03)],
                       fill=robe_l, width=int(H * .018 * s), joint="curve")                                                                      # drape highlight
                for fx0, fx1 in ((-.35, -.6), (.1, .28), (-.1, -.2)):                                                                           # folds
                    d.line([P(hip[0] + hem * fx0, hip[1] + H * .06), P(hip[0] + hem * fx1 + sway, bot - H * .015)], fill=robe_d, width=max(2, int(H * .008 * s)))
                if e.get("beads", True):
                    for i in range(11):
                        u = i / 10; bx_ = sho[0] - tw * .3 + u * tw * .75; by_ = sho[1] + H * .012 + math.sin(u * math.pi) * H * .075
                        circ(bx_, by_, H * .01, C("#4a2c1d"))
            elif pal.get("dress") and not e.get("silhouette"):
                dl = L(pal["shirt"], .32); dd_ = C(pal["shirt"], dk=.22); sash = C(e.get("sash", "#f2c14e"))
                sway = math.sin(now * 1.4 + ph) * H * .006 + sw * H * .015
                waist = hip[1] - H * .03; hemy = -H * .17; flare = H * .19
                d.polygon([P(hip[0] - H * .1, waist), P(hip[0] + H * .1, waist), P(hip[0] + flare + sway, hemy), P(hip[0] - flare + sway, hemy)], fill=shirt)   # skirt
                for i in range(7):                                                                                                                       # scalloped hem
                    u = i / 6; cx_ = hip[0] - flare + sway + u * flare * 2; circ(cx_, hemy, H * .03, shirt)
                d.line([P(hip[0] - flare * .97 + sway, hemy - H * .02), P(hip[0] + flare * .97 + sway, hemy - H * .02)], fill=dl, width=int(H * .016 * s))    # hem trim
                for fx0, fx1 in ((-.04, -.11), (.04, .1)):                                                                                                # folds
                    d.line([P(hip[0] + H * fx0, waist + H * .03), P(hip[0] + H * fx1 + sway, hemy - H * .04)], fill=dd_, width=max(2, int(H * .009 * s)))
                tw = tw_s * .85
                d.polygon([P(sho[0] - tw, sho[1]), P(sho[0] + tw, sho[1]), P(hip[0] + H * .09, waist + H * .005), P(hip[0] - H * .09, waist + H * .005)], fill=shirt)  # bodice
                circ(sho[0] - tw * .8, sho[1] + H * .02, H * .04, shirt); circ(sho[0] + tw * .8, sho[1] + H * .02, H * .04, shirt)
                X0, Y0 = P(sho[0] - H * .035, sho[1] - H * .03); X1, Y1 = P(sho[0] + H * .07, sho[1] + H * .045)
                d.chord([min(X0, X1), Y0, max(X0, X1), Y1], 0, 180, fill=skin)                                                                        # neckline
                d.polygon([P(hip[0] - H * .095, waist - H * .012), P(hip[0] + H * .095, waist - H * .012), P(hip[0] + H * .1, waist + H * .02), P(hip[0] - H * .1, waist + H * .02)], fill=sash)   # sash
                circ(hip[0] - H * .1, waist + H * .004, H * .022, sash)
            elif pal.get("robe") or pal.get("dress"):
                hem = H * (.2 if pal.get("robe") else .17)
                d.polygon([P(sho[0] - tw_s, sho[1]), P(sho[0] + tw_s, sho[1]), P(hip[0] + hem, -H * .07), P(hip[0] - hem, -H * .07)], fill=shirt)
                if pal.get("robe"): d.line([P(sho[0] - tw_s * .6, sho[1]), P(hip[0] + tw_s, hip[1] + H * .1)], fill=C(pal["shirt"], dk=.25), width=int(H * .03 * s))
            else:
                x0, y0 = P(sho[0] - tw_s, sho[1]); x1, y1 = P(hip[0] + tw_h, hip[1] + H * .05)
                d.rounded_rectangle([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)], radius=int(H * .06 * s), fill=shirt)
                if not e.get("silhouette"):
                    xb0, _ = P(sho[0] - tw_s, sho[1]); xb1, _ = P(sho[0] - tw_s * .45, sho[1])                           # back-side shade
                    d.rounded_rectangle([min(xb0, xb1), min(y0, y1) + H * .02 * s, max(xb0, xb1), max(y0, y1) - H * .01 * s], radius=int(H * .04 * s), fill=shirt_b)
                    if kind == "child":
                        d.chord([*P(sho[0] - H * .045, sho[1] - H * .025), *P(sho[0] + H * .075, sho[1] + H * .03)] if face > 0 else
                                [*P(sho[0] + H * .075, sho[1] - H * .025), *P(sho[0] - H * .045, sho[1] + H * .03)], 0, 180, fill=skin)       # round neck
                        circ(sho[0] + H * .06, sho[1] + H * .12, H * .03, L(pal["shirt"], .45))                                              # t-shirt print
                    else:
                        d.polygon([P(sho[0] - H * .02, sho[1] - H * .004), P(sho[0] + H * .07, sho[1] - H * .004), P(sho[0] + H * .03, sho[1] + H * .07)], fill=skin)  # open neck
                        cl = L(pal["shirt"], .35) if hexc(pal["shirt"])[0] < 225 else C(pal["shirt"], dk=.12)
                        d.polygon([P(sho[0] - H * .035, sho[1] - H * .012), P(sho[0] + H * .015, sho[1] + H * .045), P(sho[0] - H * .045, sho[1] + H * .04)], fill=cl)   # collar
                        d.polygon([P(sho[0] + H * .085, sho[1] - H * .012), P(sho[0] + H * .045, sho[1] + H * .045), P(sho[0] + H * .1, sho[1] + H * .04)], fill=cl)
                        for i in range(3): circ(sho[0] + H * .03 + (hip[0] - sho[0]) * (i + 1) / 4, sho[1] + H * .1 + i * (hip[1] - sho[1] - H * .08) / 3, H * .009, C(pal["shirt"], dk=.3))   # buttons
                    if not pal.get("sarong"):
                        d.line([P(hip[0] - tw_h * .95, hip[1] + H * .045), P(hip[0] + tw_h * .95, hip[1] + H * .045)], fill=C("#2f241d"), width=int(H * .02 * s))   # belt
                        circ(hip[0] + tw_h * .5, hip[1] + H * .045, H * .014, C("#c9a24a"))
                if pal.get("sarong"):
                    d.polygon([P(hip[0] - tw_h * 1.05, hip[1] + H * .02), P(hip[0] + tw_h * 1.05, hip[1] + H * .02),
                               P(hip[0] + tw_h * 1.25, -H * .14), P(hip[0] - tw_h * 1.25, -H * .14)], fill=pants)
                    d.line([P(hip[0] - tw_h, hip[1] + H * .03), P(hip[0] + tw_h, hip[1] + H * .03)], fill=C(pal["pants"], dk=.3), width=int(H * .02 * s))
                    if not e.get("silhouette"):   # checked sarong stripes
                        for yy in (.2, .27):
                            d.line([P(hip[0] - tw_h * (1.05 + yy * .4), -H * yy), P(hip[0] + tw_h * (1.05 + yy * .4), -H * yy)], fill=L(pal["pants"], .25), width=max(2, int(H * .012 * s)))
                if pal.get("bag") and not pal.get("shade"):   # bag colour that stands out from the shirt
                    r_, g_, b_, _ = hexc(pal["shirt"]); pal["shade"] = "#2f4f7a" if r_ > b_ + 40 else "#c2463b"
                if pal.get("bag"):
                    d.rounded_rectangle([*P(sho[0] - tw_s * 1.5, sho[1] + H * .03), *P(sho[0] - tw_s * .7, hip[1])] if face > 0 else
                                        [*P(sho[0] - tw_s * .7, sho[1] + H * .03), *P(sho[0] - tw_s * 1.5, hip[1])], radius=int(H * .03 * s), fill=C(pal.get("shade") or "#c2463b"))
                    d.line([P(sho[0] - tw_s * .8, sho[1] + H * .005), P(sho[0] + tw_s * .7, hip[1] - H * .02)], fill=C(pal.get("shade") or "#c2463b", dk=.25), width=int(H * .022 * s))   # strap
            # neck + head
            hr = H * (.115 if kind == "child" else .1)
            hc = (sho[0] + H * .015 + (H * .02 if anim == "laugh" else 0) + nod * .4, sho[1] - hr * 1.05 - (math.sin(now * 9) * 2 * sc if anim == "laugh" else 0) + nod)
            limb([(sho[0], sho[1]), (hc[0], hc[1] + hr * .6)], skin, H * .05)
            circ(hc[0], hc[1], hr, skin)
            if kind == "monk" and not e.get("silhouette"):   # shaved head: soft shine
                circ(hc[0] + hr * .12, hc[1] - hr * .5, hr * .3, L(pal["skin"], .12)); circ(hc[0] + hr * .2, hc[1] - hr * .58, hr * .13, L(pal["skin"], .3))
            if not e.get("silhouette"):   # ear (drawn before the hair so hair can cover its top)
                circ(hc[0] - hr * .55, hc[1] + hr * .2, hr * .19, skin); circ(hc[0] - hr * .53, hc[1] + hr * .22, hr * .085, C(pal["skin"], dk=.16))
            hair = pal.get("hair")
            if hair and kind != "old":
                X, Y = P(hc[0], hc[1]); R = hr * s * 1.04
                Y -= hr * .2 * s; d.pieslice([X - R, Y - R, X + R, Y + R], 180, 360, fill=C(hair))   # hairline above the brows
                bx = hc[0] - hr * .55; circ(bx, hc[1] - hr * .1, hr * .5, C(hair))                         # back of head
                if pal.get("bun"): circ(hc[0] - hr * .95, hc[1] - hr * .45, hr * .42, C(hair))
            if kind == "old":
                X, Y = P(hc[0], hc[1]); R = hr * s * 1.02
                a0, a1 = (115, 235) if face > 0 else (-55, 65)
                d.arc([X - R, Y - R, X + R, Y + R], a0, a1, fill=C(pal["hair"]), width=int(hr * .42 * s))
                d.pieslice([*P(hc[0] - hr * .2, hc[1] + hr * .1), *P(hc[0] + hr * .9, hc[1] + hr * 1.1)] if face > 0 else
                           [*P(hc[0] + hr * .9, hc[1] + hr * .1), *P(hc[0] - hr * .2, hc[1] + hr * 1.1)], 0, 180, fill=C(pal["hair"]))   # beard
            # ---- face (3/4 view): ear, eyebrows, eyes with whites and shine, nose, expressive mouth, blush
            if not e.get("silhouette"):
                fx_ = e.get("face")
                if isinstance(fx_, list): fx_ = ([v for tt, v in fx_ if tt <= t] or [fx_[0][1]])[-1]
                expr = fx_ or {"laugh": "laugh", "cheer": "happy", "wave": "happy", "think": "think"}.get(anim, "serene" if kind == "monk" else "calm")
                ink = C("#1b1410"); lw = max(2, int(hr * .07 * s))
                skin_d = C(pal["skin"], dk=.16); skin_dd = C(pal["skin"], dk=.3)
                brow = C(pal["hair"], dk=.15) if pal.get("hair") and kind != "old" else (C(pal["hair"]) if kind == "old" else skin_dd)
                # ear on the back side of the head
                ey = hc[1] + hr * .08; eyes = [(hc[0] + hr * .46, 1.0), (hc[0] - hr * .08, .82)]   # near eye, far eye
                blink = (now * 1.0 + ph) % 3.4 < .12
                look = .045 * hr + (math.sin(now * .7 + ph) * .02 * hr)
                for ex, k in eyes:
                    rx, ry = hr * .15 * k, hr * .19
                    if expr == "serene":                    # peaceful, gently closed eyes
                        X0, Y0 = P(ex - rx, ey - ry * .9); X1, Y1 = P(ex + rx, ey + ry * .5)
                        d.arc([min(X0, X1), Y0, max(X0, X1), Y1], 20, 160, fill=ink, width=lw); continue
                    if expr == "laugh" or blink:          # closed: happy arcs when laughing, flat line when blinking
                        X0, Y0 = P(ex - rx, ey - ry * .5); X1, Y1 = P(ex + rx, ey + ry * .7)
                        if expr == "laugh": d.arc([min(X0, X1), Y0, max(X0, X1), Y1], 200, 340, fill=ink, width=lw)
                        else: d.line([P(ex - rx, ey + ry * .1), P(ex + rx, ey + ry * .1)], fill=ink, width=lw)
                        continue
                    sq = .7 if expr in ("angry", "think") else (1.15 if expr == "surprised" else 1.0)
                    X0, Y0 = P(ex - rx, ey - ry * sq); X1, Y1 = P(ex + rx, ey + ry * sq)
                    d.ellipse([min(X0, X1), Y0, max(X0, X1), Y1], fill=(250, 247, 240, 255))
                    pr = hr * .105 * k * (.8 if expr == "surprised" else 1); circ(ex + look, ey + ry * .1, pr, ink)
                    circ(ex + look + pr * .35, ey - pr * .25, pr * .38, (255, 255, 255, 255))                    # shine
                    d.arc([min(X0, X1), Y0, max(X0, X1), Y1], 195, 345, fill=ink, width=max(2, int(lw * .8)))   # upper lid
                    if kind == "villager_f":                                                                     # lashes
                        lx, ly = P(ex + rx * .95, ey - ry * .55); lx2, ly2 = P(ex + rx * 1.3, ey - ry * .95)
                        d.line([(lx, ly), (lx2, ly2)], fill=ink, width=max(2, int(lw * .8)))
                # eyebrows: shape carries the emotion
                bw = max(2, int(hr * .085 * s))
                for i, (ex, k) in enumerate(eyes):
                    inner, outer = (ex - hr * .16 * k, ex + hr * .17 * k) if i == 0 else (ex + hr * .14 * k, ex - hr * .16 * k)
                    by = ey - hr * .27
                    di, do = {"angry": (.12, -.06), "sad": (-.1, .06), "worried": (-.1, .04), "surprised": (-.12, -.12),
                              "happy": (-.04, -.04), "serene": (-.02, .03), "laugh": (-.06, -.06), "think": ((-.12, -.12) if i == 0 else (.05, .05))}.get(expr, (0, 0))
                    d.line([P(inner, by + di * hr), P((inner + outer) / 2, by - hr * .05 + (di + do) / 2 * hr), P(outer, by + do * hr)], fill=brow, width=bw, joint="curve")
                # nose
                nx, ny = hc[0] + hr * .3, hc[1] + hr * .38
                d.arc([*P(nx - hr * .02, ny - hr * .14), *P(nx + hr * .2, ny + hr * .06)] if face > 0 else [*P(nx + hr * .2, ny - hr * .14), *P(nx - hr * .02, ny + hr * .06)],
                      -60 if face > 0 else 60, 120 if face > 0 else 240, fill=skin_dd, width=max(2, int(lw * .8)))
                # blush
                sk = hexc(pal["skin"]); ck = tuple(int(a * .72 + b * .28) for a, b in zip(sk[:3], (235, 120, 115))) + (255,)
                circ(hc[0] + hr * .58, hc[1] + hr * .44, hr * .13, ck)
                # mouth
                mx, my = hc[0] + hr * .3, hc[1] + hr * .64
                lip = C("#a8443c") if kind == "villager_f" else C("#5a2a20")
                def box(x0, y0, x1, y1):
                    X0, Y0 = P(x0, y0); X1, Y1 = P(x1, y1); return [min(X0, X1), min(Y0, Y1), max(X0, X1), max(Y0, Y1)]
                if expr in ("laugh", "happy") and talk <= .12 and anim in ("laugh", "cheer", "wave"):
                    w2 = hr * (.27 if expr == "laugh" else .22)
                    d.pieslice(box(mx - w2, my - hr * .16, mx + w2, my + hr * (.26 if expr == "laugh" else .18)), 0, 180, fill=C("#5a1e1a"))
                    d.chord(box(mx - w2 * .8, my - hr * .02, mx + w2 * .8, my + hr * .08), 0, 180, fill=(250, 247, 240, 255))       # teeth
                    d.chord(box(mx - w2 * .5, my + hr * .06, mx + w2 * .5, my + hr * (.24 if expr == "laugh" else .17)), 180, 360, fill=C("#c9605a"))  # tongue
                elif talk > .12:
                    op = hr * (.06 + .22 * min(1, talk)); d.ellipse(box(mx - hr * .15, my - op * .5, mx + hr * .15, my + op * .5), fill=C("#5a1e1a"))
                    if op > hr * .14: d.chord(box(mx - hr * .11, my - op * .5, mx + hr * .11, my - op * .5 + hr * .08), 180, 360, fill=(250, 247, 240, 255))
                elif expr == "surprised":
                    d.ellipse(box(mx - hr * .08, my - hr * .08, mx + hr * .08, my + hr * .1), fill=C("#5a1e1a"))
                elif expr in ("sad", "worried"):
                    d.arc(box(mx - hr * .17, my, mx + hr * .17, my + hr * .2), 200, 340, fill=lip, width=lw)
                elif expr == "angry":
                    d.line([P(mx - hr * .15, my + hr * .05), P(mx + hr * .15, my + hr * .02)], fill=lip, width=lw)
                elif expr == "think":
                    d.line([P(mx - hr * .1, my + hr * .04), P(mx + hr * .14, my - hr * .02)], fill=lip, width=lw)
                else:   # calm / happy: soft smile
                    d.arc(box(mx - hr * .2, my - hr * .12, mx + hr * .2, my + hr * (.12 if expr == "happy" else .08)), 20, 160, fill=lip, width=lw)
            if pal.get("hat") == "straw":
                d.polygon([P(hc[0] - hr * 2.3, hc[1] - hr * .45), P(hc[0] + hr * .1, hc[1] - hr * 1.95), P(hc[0] + hr * 2.4, hc[1] - hr * .45)], fill=C("#d9b26a"))
                d.line([P(hc[0] - hr * 1.6, hc[1] - hr * .75), P(hc[0] + hr * 1.7, hc[1] - hr * .75)], fill=C("#a8823f"), width=int(H * .014 * s))
            # ---- front arm + props
            hd = arm(1, skin if (pal.get("robe") and not e.get("silhouette")) else shirt, skin)   # monk's front arm is bare
            if anim == "carry":
                circ(hd[0] + H * .03, hd[1] - H * .05, H * .085, C(e.get("stone", "#8f897c"))); circ(hd[0] + H * .01, hd[1] - H * .08, H * .025, C("#b9b3a6"))
            if pal.get("staff"):
                if anim in ("think", "wave", "cheer", "laugh", "sit", "carry"):   # hand is busy: the stick leans beside him
                    sx = sho[0] + H * .3
                    d.line([P(sx - H * .03, sho[1] + H * .02), P(sx + H * .02, -2)], fill=C("#6b4a2b"), width=int(H * .025 * s))
                else:
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

    def tea(self, e, t, now):
        """Low tea table with a cup; `fill` 0..1 fills the cup, above 1 overflows into a spreading puddle.
        `pour` 0/1 shows a stream from above (the pourer's hand should be near x, y-170)."""
        x, y = kf(e.get("x", 540), t), kf(e.get("y", self.ground), t)
        fill, pour = kf(e.get("fill", 0), t), kf(e.get("pour", 0), t)
        def f(d, s):
            def R(a, b, c, dd, col, r=0): d.rounded_rectangle([a * s, b * s, c * s, dd * s], radius=int(r * s), fill=col)
            R(x - 150, y - 70, x + 150, y - 52, hexc("#6b4a2b"), 6)                      # table top
            R(x - 130, y - 54, x - 112, y, hexc("#5a3d23"), 3); R(x + 112, y - 54, x + 130, y, hexc("#5a3d23"), 3)
            if fill > 1:                                                                  # spill on the table and down
                w = min(140, 30 + (fill - 1) * 220)
                d.ellipse([(x - w) * s, (y - 76) * s, (x + w) * s, (y - 62) * s], fill=hexc("#b5763a", 220))
                if fill > 1.3:
                    for k, dx in enumerate((-w * .7, w * .6)):
                        L = min(52, (fill - 1.3) * 160)
                        d.line([((x + dx) * s, (y - 56) * s), ((x + dx) * s, (y - 56 + L) * s)], fill=hexc("#b5763a", 220), width=int(6 * s))
            cx, top, bot = x, y - 128, y - 70
            d.polygon([((cx - 34) * s, top * s), ((cx + 34) * s, top * s), ((cx + 24) * s, bot * s), ((cx - 24) * s, bot * s)], fill=hexc("#f2ece0"))
            lvl = top + (bot - top) * (1 - min(1, fill)) + 4
            if fill > 0.02:
                frac = (lvl - top) / (bot - top); hw = 34 - 10 * frac
                d.polygon([((cx - hw + 3) * s, lvl * s), ((cx + hw - 3) * s, lvl * s), ((cx + 22) * s, (bot - 3) * s), ((cx - 22) * s, (bot - 3) * s)], fill=hexc("#b5763a"))
            d.arc([(cx + 26) * s, (top + 14) * s, (cx + 50) * s, (top + 40) * s], -90, 90, fill=hexc("#f2ece0"), width=int(6 * s))
            d.line([((cx - 34) * s, top * s), ((cx + 34) * s, top * s)], fill=hexc("#d8cfbf"), width=int(4 * s))
            if pour > .5:
                wob = math.sin(now * 20) * 2
                d.line([((cx - 6 + wob) * s, (y - 230) * s), ((cx - 2) * s, top * s)], fill=hexc("#b5763a", 230), width=int(7 * s))
            if fill > 1:                                                                  # overflow over the rim
                d.line([((cx - 34) * s, top * s), ((cx - 40) * s, (bot + 2) * s)], fill=hexc("#b5763a", 230), width=int(6 * s))
                d.line([((cx + 34) * s, top * s), ((cx + 40) * s, (bot + 2) * s)], fill=hexc("#b5763a", 230), width=int(6 * s))
            for k in range(3):                                                            # steam
                ph = (now * .6 + k / 3) % 1; sx = cx - 14 + k * 14 + math.sin(now * 2 + k) * 6
                d.ellipse([(sx - 7) * s, (top - 20 - ph * 60) * s, (sx + 7) * s, (top - 6 - ph * 60) * s], fill=(255, 255, 255, int(110 * (1 - ph))))
        return hi(f, (W, H)), (0, 0)

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
            if e.get("box"):
                tw = max(font.getlength(ln) for ln in lines); pad = e.get("size", 70) * .45
                d.rounded_rectangle([W / 2 - tw / 2 - pad, 20 - pad * .3, W / 2 + tw / 2 + pad, 20 + lh * len(lines) + pad * .3],
                                    radius=int(pad), fill=hexc(e["box"], 225))
            for i, ln in enumerate(lines):
                d.text((W / 2, 20 + i * lh + lh / 2), ln, font=font, anchor="mm", fill=hexc(e.get("color", "#ffffff")),
                       stroke_width=e.get("stroke", 0), stroke_fill=(10, 10, 20, 255))
            self.cache[key] = im
        im = self.cache[key]
        cx = kf(e.get("x", W / 2), t)                       # optional horizontal centre (default: middle)
        return self._alpha(im, a), (int(cx - W / 2), int(kf(e.get("y", 300), t) - im.height / 2))

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
            elif ty == "tea": res = self.tea(e, t, now)
            elif ty == "divider":
                lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(lay); xx = e.get("x", W / 2)
                dd.line([(xx, e.get("y0", 180)), (xx, e.get("y1", self.ground))], fill=hexc(e.get("color", "#ffffff"), int(255 * kf(e.get("alpha", .7), t))), width=e.get("width", 6))
                res = (lay, (0, 0))
            elif ty in ("rain", "birds", "fireflies", "splash", "lightning"):
                lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
                if ty == "lightning": self.bolt(e, now, d)
                else: getattr(self, ty)(e, t, now, d)
                res = (lay, (0, 0))
            if res and res[0] is not None: paste_clip(img, res[0], res[1])
        if self.spec.get("dust", not any(e["type"] in ("rain", "fireflies", "splash") for e in self.els)):
            self.dust(img, now)
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
        cam = self.spec.get("camera")
        if cam is None and self.spec.get("auto_camera", True):   # gentle push-in / pull-out so no shot is ever static
            u = t * t * (3 - 2 * t); side = 1 if self.idx % 2 == 0 else -1; zin = self.idx % 3 != 2
            cam = {"zoom": 1.0 + .07 * (u if zin else 1 - u), "cx": W / 2 + side * 40 * (u - .5), "cy": H * .55}
        cam = cam or {}
        z = kf(cam.get("zoom", 1.0), t); cx = kf(cam.get("cx", W / 2), t); cy = kf(cam.get("cy", H / 2), t)
        if abs(z - 1) > 1e-3:
            cw, ch = W / z, H / z; x0 = min(max(cx - cw / 2, 0), W - cw); y0 = min(max(cy - ch / 2, 0), H - ch)
            out = out.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
        return out

def _dust(self, img, now):
    if not hasattr(self, "_specks"):
        r = random.Random(self.idx * 7 + 3)
        self._specks = [(r.random() * W, r.random() * self.ground * .95, r.uniform(2, 5), r.uniform(.15, .45), r.random() * 6.28, r.uniform(40, 95)) for _ in range(26)]
        self._dlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lay = self._dlay.copy(); d = ImageDraw.Draw(lay)
    for x, y, rr, sp, ph, a in self._specks:
        xx = (x + now * 18 * sp + math.sin(now * sp * 2 + ph) * 22) % W; yy = (y - now * 26 * sp) % (self.ground * .95)
        al = int(a * (.55 + .45 * math.sin(now * 1.7 + ph)))
        d.ellipse([xx - rr, yy - rr, xx + rr, yy + rr], fill=(255, 244, 214, al))
    img.alpha_composite(lay)
Scene.dust = _dust

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
    gold = (255, 214, 140, 235)                                       # little stopwatch
    d.ellipse([16, 16, 44, 44], outline=gold, width=4)
    d.rectangle([27, 9, 33, 13], fill=gold); d.line([(30, 30), (30, 21)], fill=gold, width=3); d.line([(30, 30), (36, 33)], fill=gold, width=3)
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
    add_signature(story, out, sr)
    return out, sr

def add_signature(story, out, sr):
    """Recorded intro (start of scene 1) and outro (end of the last scene) in the SAME gender as the story voice:
    voice/male/ for am_*/bm_* stories, voice/female/ for af_*/bf_*. Rotates through the files per video.
    Story keys "intro"/"outro": 0 leaves it out, or a file name like "intro_03.wav" to pick one."""
    import soundfile as sf, datetime, glob
    gender = "female" if story.get("voice", "bm_george")[1:2] == "f" else "male"
    vdir = os.path.join(HERE, "..", "voice", gender)
    if not os.path.isdir(vdir) or not out: return
    try: lines = json.load(open(os.path.join(HERE, "..", "voice", "lines.json")))
    except Exception: lines = {}
    try: day = datetime.date.fromisoformat(story.get("publish_date", "")).toordinal()
    except ValueError: day = sum(map(ord, story.get("title", "")))
    slot = day * 2 + (1 if story.get("publish_at", "05:45") >= "12:00" else 0)
    allv = np.concatenate([o["audio"] for o in out]); ref = np.sqrt(np.mean(allv[np.abs(allv) > .02] ** 2))   # loudness of the story voice
    for kind in ("intro", "outro"):
        takes = sorted(os.path.basename(f) for f in glob.glob(os.path.join(vdir, f"{kind}_*.wav")))
        pick = story.get(kind)
        if pick == 0 or not takes: continue
        name = pick if pick in takes else takes[(slot if kind == "intro" else slot + slot // 2 + 1) % len(takes)]
        a, r = sf.read(os.path.join(vdir, name), dtype="float32")
        if a.ndim > 1: a = a.mean(1)
        if r != sr: a = np.interp(np.arange(int(len(a) * sr / r)) * r / sr, np.arange(len(a)), a).astype(np.float32)
        a *= min(4.0, ref / (np.sqrt(np.mean(a[np.abs(a) > .02] ** 2)) + 1e-9))
        d = len(a) / sr; text = lines.get(f"{gender}/{name}", "")
        caps = chunk_halves(text) if text else []
        if kind == "intro":
            sc = out[0]; lead = .35; pad = .45
            sc["audio"] = np.concatenate([np.zeros(int(lead * sr), np.float32), a, np.zeros(int(pad * sr), np.float32), sc["audio"]])
            shift = lead + d + pad
            for c in sc["chunks"]: c["start"] += shift; c["end"] += shift
            sc["chunks"][:0] = [{"text": t, "start": lead + d * i / len(caps), "end": lead + d * (i + 1) / len(caps)} for i, t in enumerate(caps)]
            sc["dur"] += shift
        else:
            sc = out[-1]; start = len(sc["audio"]) / sr + .2
            sc["audio"] = np.concatenate([sc["audio"], np.zeros(int(.2 * sr), np.float32), a, np.zeros(int(.6 * sr), np.float32)])
            sc["chunks"] += [{"text": t, "start": start + d * i / len(caps), "end": start + d * (i + 1) / len(caps)} for i, t in enumerate(caps)]
            sc["dur"] = max(sc["dur"], len(sc["audio"]) / sr)

def chunk_halves(text):
    w = text.split(); h = (len(w) + 1) // 2
    return [" ".join(w[:h]), " ".join(w[h:])] if len(w) > 4 else [text]

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
    # TikTok only pays for videos of 60 s or more: hold the final card longer if the story runs short.
    total = sum(v["dur"] for v in voice); min_total = float(story.get("min_seconds", 62))
    if total < min_total:
        voice[-1]["dur"] += min_total - total
        print(f"Story ran {total:.1f}s; holding the last card {min_total - total:.1f}s longer to reach {min_total:.0f}s")
    hl = set(w.lower() for w in story.get("highlight", []))
    caps = Captions(); files = []; prev_raw = None; last_raw = None; XF = int(.4 * FPS)
    wm = make_watermark(story.get("watermark", "Mindset Minute"))
    for i, (sc, vo) in enumerate(zip(story["scenes"], voice)):
        dur = vo["dur"]; nfr = int(round(dur * FPS)); vo["nfr"] = nfr
        a = vo["audio"]; spf = sr / FPS
        env = np.array([np.sqrt(np.mean(a[int(k * spf):int((k + 1) * spf)] ** 2)) if int(k * spf) < len(a) else 0 for k in range(nfr)])
        env = np.clip(env / (np.percentile(env[env > 0], 90) if np.any(env > 0) else 1), 0, 1)
        scene = Scene(sc, dur, random.Random(i), idx=i, talk=env)
        tmp = os.path.join(work, f"s{i:02d}.tmp.mp4"); fin = os.path.join(work, f"s{i:02d}.mp4")
        p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                              "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS), tmp], stdin=subprocess.PIPE)
        for f in range(nfr):
            now = f / FPS; raw = scene.frame(now)
            if prev_raw is not None and f < XF and not sc.get("cut"):   # soft dissolve from the previous scene
                raw = Image.blend(prev_raw, raw, (f + 1) / (XF + 1))
            if f == nfr - 1: last_raw = raw
            fr = raw.convert("RGBA")
            if sc.get("captions", True): caps.draw(fr, vo["chunks"], now, sc.get("caption_y", 700), hl)
            if wm is not None and sc.get("watermark", True): fr.alpha_composite(wm, dest=(W - wm.width - 36, 330))
            p.stdin.write(fr.convert("RGB").tobytes())
        p.stdin.close(); prev_raw = last_raw
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
        si = int(si); sc = story["scenes"][si]; scene = Scene(sc, sc.get("preview_dur", 8), random.Random(si), idx=si)
        fr = scene.frame(ts).convert("RGBA")
        wm = make_watermark(story.get("watermark", "Mindset Minute"))
        if wm is not None and sc.get("watermark", True): fr.alpha_composite(wm, dest=(W - wm.width - 36, 330))
        if sc.get("captions", True): Captions().draw(fr, [{"text": "Sample caption text here", "start": 0, "end": 99}], 1, sc.get("caption_y", 700), set(story.get("highlight", [])))
        fr.convert("RGB").save(os.path.join(outdir, f"p{si}_{ts}.jpg"), quality=88)

if __name__ == "__main__":
    if sys.argv[1] == "--stills":
        stills(sys.argv[2], sys.argv[3], [tuple(map(float, x.split(":"))) for x in sys.argv[4:]])
    else:
        render(sys.argv[1], sys.argv[2])
