#!/usr/bin/env python3
"""Thumbnail brief: 3 click-worthy concepts for a creator's real video, with ready to paste image prompts.

The concepts follow what wins on YouTube now: one focal point, genuine emotion, a complementary color pair
(not YouTube red and white), 0 to 4 bold words that do not repeat the title, readable at phone size, and an
honest promise (YouTube's A/B test picks by watch time, so clickbait loses).

The raster is made by an image tool (Nano Banana / Gemini, Ideogram) or in Photopea; this writes what to make.

Run:  python thumb_brief.py "I Survived 100 Days in Hardcore Minecraft" minecraft
"""
import hashlib
import random
import re
import sys

STYLE = {
    "roblox": ("Roblox avatar character, smooth glossy plastic 3D style like a high end Roblox render, "
               "soft studio lighting with a strong colored rim light, shallow depth of field, ultra saturated"),
    "minecraft": ("Minecraft blocky voxel style, cinematic shader lighting with volumetric light, "
                  "high detail 3D render, strong colored rim light, shallow depth of field, ultra saturated"),
}
GAME = {"roblox": "Roblox", "minecraft": "Minecraft"}

# (name, trigger words, composition, color pair, focal and emotion, word options)
CONCEPTS = [
    ("VS split", r"\bvs\.?\b|noob|\bpro\b|hacker|god|1 vs|versus|rich|poor",
     "frame split diagonally into two halves, one character on each side facing each other",
     "electric blue vs hot orange", "both characters mid reaction, one confident, one panicking",
     ["NOOB VS PRO", "WHO WINS?", "1 VS 100"]),
    ("Survival hero", r"100 days|survived|surviving|hardcore|\bdays\b|lasted|alone",
     "character large in the right third, battered and determined, the biggest threat of the video looming in the left background",
     "deep red vs gold", "tired but determined face, looking straight at the viewer",
     ["DAY 100", "I SURVIVED", "100 DAYS"]),
    ("Danger moment", r"trapped|escape|prison|obby|lava|tsunami|flood|fall|stuck|jail|run",
     "character caught mid action at the edge of the danger, the hazard filling the bottom of the frame",
     "lava orange vs teal", "pure shock, mouth open, eyes wide",
     ["DON'T FALL", "NO ESCAPE?", "TRAPPED"]),
    ("Secret reveal", r"secret|hidden|base|spy|mystery|found|discovered|underground|room",
     "character peeking around a wall or block, the hidden thing glowing in the background with a soft circle of light",
     "purple vs neon green", "curious, wide eyes, finger to lips or pointing",
     ["SECRET BASE", "HIDDEN?", "THEY DON'T KNOW"]),
    ("Scary", r"horror|scary|3 ?am|ghost|monster|creepy|haunted|backrooms|herobrine|night",
     "character in the foreground lit by a flashlight, a dark silhouette of the monster close behind them",
     "cold cyan vs black, one small red accent", "terrified, looking back over the shoulder",
     ["BEHIND YOU", "DON'T LOOK", "3:00 AM"]),
    ("Build reveal", r"build|house|castle|mansion|city|made|built|redstone|farm",
     "the finished build huge and glowing behind the character, character small in the front pointing at it, golden hour light",
     "warm gold vs sky blue", "proud, excited, arms open",
     ["MY BEST BUILD", "IT WORKED", "BEFORE / AFTER"]),
    ("Story drama", r"story|lied|betray|family|mom|dad|sister|brother|girlfriend|boyfriend|sad|adopted",
     "two characters close up, one in focus in the front with a strong emotion, the other blurred behind",
     "cool blue vs warm pink", "big emotion on the front character: shock, tears or anger",
     ["SHE LIED", "WHY?", "THE TRUTH"]),
    ("Object hero", r"$^",
     "the single most important item, mob or place from the video huge in the center, glowing, slightly tilted toward the viewer, no clutter around it",
     "gold glow vs deep navy", "no face needed; the object carries the curiosity, add a small surprised character in a corner only if it helps",
     ["WAS IT WORTH IT?", "1 IN A MILLION", "FOUND IT"]),
    ("Reaction close-up", r".",
     "one character very large, cropped at the shoulders on the right, the key object or place of the video on the left",
     "yellow vs royal blue", "strong genuine reaction that matches what happens in the video",
     ["WAIT WHAT", "NO WAY", "IT HAPPENED"]),
]


def pick(title):
    t = (title or "").lower()
    safe = [c for c in CONCEPTS if c[0] in ("Reaction close-up", "Object hero")]
    hits = [c for c in CONCEPTS if c not in safe and re.search(c[1], t)]
    seen, out = set(), []
    for c in hits + safe:  # concepts that match the video, then the two that fit any video honestly
        if c[0] not in seen:
            seen.add(c[0]); out.append(c)
    return out[:3]


def words_not_in_title(options, title, rng=None):
    tw = set(re.findall(r"\w+", (title or "").lower()))
    good = [o for o in options if not set(re.findall(r"\w+", o.lower())) <= tw]
    return (good + [o for o in options if o not in good])[:2]


def brief(title, niche="roblox", seed=""):
    niche = niche if niche in STYLE else "roblox"
    rng = random.Random(int(hashlib.sha256((title + seed).encode()).hexdigest()[:8], 16))
    lines = [f"THUMBNAIL BRIEF for \"{title}\" ({GAME[niche]})",
             "Rules: one focal point, real emotion, 0 to 4 words that do not repeat the title, readable at phone size,"
             " nothing important in the bottom right corner. Make all three, send the best as the sample."]
    for i, (name, _, comp, colors, emotion, opts) in enumerate(pick(title), 1):
        words = words_not_in_title(opts, title, rng)
        subject = re.sub(r"\s*[\(\[].*?[\)\]]|#\w+", "", title).strip()
        prompt = (f"YouTube thumbnail, 16:9, for a {GAME[niche]} video called \"{subject}\". {comp}. "
                  f"{emotion}. Color palette {colors}, high contrast, clean simple background. {STYLE[niche]}. "
                  f"No text, no logos, no watermark.")
        lines += ["", f"{i}. {name}",
                  f"Layout: {comp}.", f"Emotion: {emotion}.", f"Colors: {colors}.",
                  f"Words (pick one): {' / '.join(words)}",
                  f"Image prompt (Nano Banana or Ideogram; attach their current thumbnail or a screenshot as reference):",
                  prompt]
    lines += ["", "Then add the words in Photopea or the Forge: heavy font, thick dark outline, text on the side away from the face."]
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('usage: python thumb_brief.py "video title" [roblox|minecraft]')
    print(brief(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "roblox"))
