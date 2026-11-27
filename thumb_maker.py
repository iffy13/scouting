#!/usr/bin/env python3
"""Thumbnail maker: real, finished thumbnail samples made by Google's image model (Nano Banana Pro).

For a creator's video it:
  1. downloads their current thumbnail (the BEFORE),
  2. picks 3 concepts that fit the video (thumb_brief.py),
  3. asks the Gemini image model for each one, with their thumbnail attached so the character, game and setting
     stay theirs, and the words rendered in,
  4. builds a before and after image for each,
  5. sends everything to your Telegram.

Needs: GEMINI_API_KEY (Google AI Studio, with billing on: image models are paid, a few cents per image),
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID. Optional: GEMINI_IMAGE_MODEL to force a model (otherwise the best image
model the key can use is picked, preferring the Pro one), YOUTUBE_API_KEY (video title lookup).

Run:  python thumb_maker.py https://www.youtube.com/watch?v=VIDEO_ID [roblox|minecraft] ["optional title"]
      python thumb_maker.py --selftest
"""
import base64
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from thumb_brief import pick, words_not_in_title, STYLE, GAME

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
FORCED_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "").strip()
YOUTUBE_KEY = os.getenv("YOUTUBE_API_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
API = "https://generativelanguage.googleapis.com/v1beta"
OUT_DIR = os.getenv("THUMB_OUT", "thumb_samples")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36"}


# ---------------------------------------------------------------- inputs
def video_id(text):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([\w-]{11})", text or "")
    return m.group(1) if m else (text if re.fullmatch(r"[\w-]{11}", text or "") else "")


def get(url, timeout=40):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def video_title(vid):
    if YOUTUBE_KEY:
        try:
            q = urllib.parse.urlencode({"part": "snippet", "id": vid, "key": YOUTUBE_KEY})
            items = json.loads(get(f"https://www.googleapis.com/youtube/v3/videos?{q}")).get("items", [])
            if items:
                return items[0]["snippet"]["title"]
        except Exception as e:
            print(f"title lookup via API failed: {e}")
    try:
        u = urllib.parse.quote(f"https://www.youtube.com/watch?v={vid}", safe="")
        return json.loads(get(f"https://www.youtube.com/oembed?url={u}&format=json")).get("title", "")
    except Exception:
        return ""


def current_thumbnail(vid):
    for name in ("maxresdefault", "sddefault", "hqdefault"):
        try:
            data = get(f"https://i.ytimg.com/vi/{vid}/{name}.jpg")
            if len(data) > 5000:  # YouTube serves a tiny grey placeholder when a size is missing
                return data
        except Exception:
            continue
    return b""


# ---------------------------------------------------------------- the model
def api(path, body=None):
    url = f"{API}/{path}{'&' if '?' in path else '?'}key={GEMINI_KEY}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def pick_model():
    """The best image model this key can use: a 'pro' image model first, then any image model."""
    if FORCED_MODEL:
        return FORCED_MODEL
    names, token = [], ""
    for _ in range(5):
        data = api("models?pageSize=200" + (f"&pageToken={token}" if token else ""))
        for m in data.get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []) and "image" in m["name"].lower():
                names.append(m["name"].split("/", 1)[1])
        token = data.get("nextPageToken", "")
        if not token:
            break
    if not names:
        raise RuntimeError("this API key cannot use any Gemini image model")

    def rank(n):
        n = n.lower()
        return (0 if "pro" in n else 1, 0 if "preview" not in n and "exp" not in n else 1, n)
    names.sort(key=rank)
    print(f"image models available: {names[:6]}; using {names[0]}")
    return names[0]


def generate(model, prompt, ref_jpeg):
    parts = [{"text": prompt}]
    if ref_jpeg:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(ref_jpeg).decode()}})
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"], "imageConfig": {"aspectRatio": "16:9"}}}
    for attempt in range(3):
        try:
            data = api(f"models/{model}:generateContent", body)
            break
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "ignore")
            if e.code == 400 and "imageConfig" in msg and "imageConfig" in body["generationConfig"]:
                body["generationConfig"].pop("imageConfig")  # older models do not take an aspect ratio
                continue
            if e.code in (429, 500, 503) and attempt < 2:
                time.sleep(20 * (attempt + 1))
                continue
            raise RuntimeError(f"image model said HTTP {e.code}: {msg}")
    for cand in data.get("candidates", []):
        for p in cand.get("content", {}).get("parts", []):
            blob = p.get("inline_data") or p.get("inlineData")
            if blob and blob.get("data"):
                return base64.b64decode(blob["data"])
    reason = (data.get("candidates") or [{}])[0].get("finishReason", "") or data.get("promptFeedback", {})
    raise RuntimeError(f"no image came back ({reason})")


def concept_prompt(title, niche, concept, words, has_ref):
    name, _, comp, colors, emotion, _ = concept
    game = GAME.get(niche, "Roblox")
    ref = ("The attached image is the creator's current thumbnail: keep THEIR character, avatar or skin, their game "
           "and their setting recognisable, but redesign the whole thumbnail to a far more professional, click-worthy "
           "standard. " if has_ref else "")
    return (
        f"{ref}Create a YouTube thumbnail, 16:9, 1280x720, for a {game} video titled \"{title}\". "
        f"Concept: {name}. Layout: {comp}. Emotion: {emotion}. Color palette: {colors}, very high contrast, "
        f"background simple and slightly blurred so the subject pops. Style: {STYLE.get(niche, STYLE['roblox'])}. "
        f"Add the words \"{words}\" in huge bold rounded sans-serif capital letters with a thick dark outline and a "
        f"soft drop shadow, on the side away from the character's face, spelled exactly like that. No other text, "
        f"no logos, no watermark, no YouTube play button. Keep the bottom right corner clear (the video length "
        f"covers it). It must read clearly at phone size and look like a top creator's thumbnail."
    )


# ---------------------------------------------------------------- output
def to_jpeg(png_or_jpeg, size=(1280, 720)):
    from PIL import Image
    im = Image.open(io.BytesIO(png_or_jpeg)).convert("RGB")
    w, h = im.size
    tw, th = size
    s = max(tw / w, th / h)
    im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
    l, t = (im.width - tw) // 2, (im.height - th) // 2
    im = im.crop((l, t, l + tw, t + th))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=92); return buf.getvalue()


def before_after(before, after, label_font=None):
    from PIL import Image, ImageDraw, ImageFont
    W, H, pad, top = 1600, 520, 20, 70
    iw = (W - pad * 3) // 2; ih = iw * 9 // 16
    canvas = Image.new("RGB", (W, H), (17, 19, 24))
    for i, data in enumerate((before, after)):
        im = Image.open(io.BytesIO(data)).convert("RGB").resize((iw, ih), Image.LANCZOS)
        canvas.paste(im, (pad + i * (iw + pad), top))
    d = ImageDraw.Draw(canvas)
    font = None
    for f in (label_font, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        try:
            if f:
                font = ImageFont.truetype(f, 40); break
        except Exception:
            continue
    font = font or ImageFont.load_default()
    d.text((pad, 18), "BEFORE", fill=(154, 161, 178), font=font)
    d.text((pad * 2 + iw, 18), "AFTER", fill=(255, 210, 31), font=font)
    buf = io.BytesIO(); canvas.save(buf, "JPEG", quality=90); return buf.getvalue()


def multipart(fields, files):
    boundary = uuid.uuid4().hex
    out = io.BytesIO()
    for k, v in fields.items():
        out.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    for k, (fname, data, ctype) in files.items():
        out.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fname}\"\r\n"
                  f"Content-Type: {ctype}\r\n\r\n".encode())
        out.write(data); out.write(b"\r\n")
    out.write(f"--{boundary}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={boundary}"


def tg_photo(data, caption, as_file=False):
    if not (TG_TOKEN and TG_CHAT):
        print(f"(no Telegram) would send photo: {caption[:80]}")
        return
    method, field = ("sendDocument", "document") if as_file else ("sendPhoto", "photo")
    body, ctype = multipart({"chat_id": TG_CHAT, "caption": caption[:1000]},
                            {field: ("thumbnail.jpg", data, "image/jpeg")})
    req = urllib.request.Request(f"https://api.telegram.org/bot{TG_TOKEN}/{method}", data=body,
                                 headers={"Content-Type": ctype})
    try:
        urllib.request.urlopen(req, timeout=60)
    except Exception as e:
        print(f"telegram photo failed: {e}")


def tg_text(text):
    if not (TG_TOKEN and TG_CHAT):
        print(text); return
    data = urllib.parse.urlencode({"chat_id": TG_CHAT, "text": text[:3900], "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data=data, timeout=30)
    except Exception as e:
        print(f"telegram failed: {e}")


# ---------------------------------------------------------------- main job
def make_samples(vid, niche="roblox", title="", who=""):
    """Makes 3 finished samples for one video and sends them to Telegram. Returns how many were made."""
    if not GEMINI_KEY:
        tg_text("Thumbnail samples skipped: add the GEMINI_API_KEY secret on GitHub to have them made automatically.")
        return 0
    title = title or video_title(vid) or "my latest video"
    before = current_thumbnail(vid)
    before_j = to_jpeg(before) if before else b""
    try:
        model = pick_model()
    except Exception as e:
        tg_text(f"Thumbnail samples failed: {e}")
        return 0
    head = f"SAMPLES for {who + ': ' if who else ''}\"{title}\" ({GAME.get(niche, 'Roblox')})\nhttps://www.youtube.com/watch?v={vid}"
    tg_text(head + f"\nMaking 3 concepts with {model}. Pick the best one, check it closely, and send it as the before and after.")
    os.makedirs(OUT_DIR, exist_ok=True)
    made = 0
    for i, concept in enumerate(pick(title), 1):
        words = words_not_in_title(concept[5], title, None)[0]
        try:
            img = to_jpeg(generate(model, concept_prompt(title, niche, concept, words, bool(before_j)), before_j))
        except Exception as e:
            print(f"concept {i} failed: {e}")
            tg_text(f"Concept {i} ({concept[0]}) failed: {str(e)[:300]}")
            continue
        made += 1
        with open(os.path.join(OUT_DIR, f"{vid}_{i}.jpg"), "wb") as f:
            f.write(img)
        cap = f"{i}. {concept[0]}  |  words: {words}\nFor \"{title}\""
        if before_j:
            ba = before_after(before_j, img)
            with open(os.path.join(OUT_DIR, f"{vid}_{i}_before_after.jpg"), "wb") as f:
                f.write(ba)
            tg_photo(ba, cap + "\nBefore and after, ready to send.")
        tg_photo(img, cap + "\nFull size 1280x720 file (send this one as the thumbnail).", as_file=True)
    if made:
        tg_text("Check each one before sending: the words spelled right, their character still looks like theirs, "
                "no extra fingers or broken blocks. If one is close but not right, run it again; every run is different.")
    return made


def selftest():
    from PIL import Image
    assert video_id("https://www.youtube.com/watch?v=abcdefghijk&t=3") == "abcdefghijk"
    assert video_id("https://youtu.be/abcdefghijk") == "abcdefghijk"
    assert video_id("https://www.youtube.com/shorts/abcdefghijk") == "abcdefghijk"
    a = io.BytesIO(); Image.new("RGB", (640, 480), (30, 90, 200)).save(a, "JPEG")
    b = io.BytesIO(); Image.new("RGB", (1024, 576), (250, 180, 20)).save(b, "PNG")
    j = to_jpeg(b.getvalue()); assert Image.open(io.BytesIO(j)).size == (1280, 720)
    ba = before_after(to_jpeg(a.getvalue()), j); assert Image.open(io.BytesIO(ba)).size == (1600, 520)
    body, ctype = multipart({"chat_id": "1"}, {"photo": ("x.jpg", b"\xff\xd8abc", "image/jpeg")})
    assert b"name=\"photo\"" in body and ctype.startswith("multipart/form-data")
    p = concept_prompt("I Survived 100 Days in Hardcore Minecraft", "minecraft", pick("100 days hardcore")[0], "DAY 100", True)
    assert "DAY 100" in p and "Minecraft" in p and "current thumbnail" in p
    print("selftest passed")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest(); sys.exit(0)
    if len(sys.argv) < 2:
        sys.exit("usage: python thumb_maker.py <youtube link> [roblox|minecraft] [\"title\"]")
    vid = video_id(sys.argv[1])
    if not vid:
        sys.exit("could not find a video id in that link")
    niche = sys.argv[2] if len(sys.argv) > 2 else "roblox"
    n = make_samples(vid, niche, sys.argv[3] if len(sys.argv) > 3 else "")
    print(f"{n} samples made")
    sys.exit(0 if n else 1)
