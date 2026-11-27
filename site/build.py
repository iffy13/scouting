#!/usr/bin/env python3
"""Builds site/works.json from the images in site/work and site/before-after.

Add a piece: put an image in site/work (or site/before-after). Name it game-title-words.jpg, for example
roblox-tower-of-doom.jpg or minecraft-100-days-skyblock.png. Files are shown in name order, so start a name with
a number (01-, 02-) to choose the order. For a nicer title or a format label, add the file to captions.json.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = re.compile(r"\.(jpe?g|png|webp|gif)$", re.I)
GAMES = ("roblox", "minecraft")


def auto(name):
    stem = IMG.sub("", name)
    stem = re.sub(r"^\d+[-_ ]*", "", stem)
    parts = [p for p in re.split(r"[-_ ]+", stem) if p]
    game = parts[0].lower() if parts and parts[0].lower() in GAMES else "other"
    words = parts[1:] if game != "other" else parts
    title = " ".join(words).strip().capitalize() or stem
    return game, title


def items(folder, caps):
    out = []
    path = os.path.join(HERE, folder)
    for name in sorted(os.listdir(path)) if os.path.isdir(path) else []:
        if not IMG.search(name):
            continue
        game, title = auto(name)
        c = caps.get(name, {})
        out.append({"src": f"{folder}/{name}", "game": c.get("game", game), "title": c.get("title", title),
                    "format": c.get("format", "")})
    return out


def main():
    try:
        with open(os.path.join(HERE, "captions.json")) as f:
            caps = json.load(f)
    except FileNotFoundError:
        caps = {}
    data = {"work": items("work", caps.get("work", {})), "beforeAfter": items("before-after", caps.get("before-after", {}))}
    with open(os.path.join(HERE, "works.json"), "w") as f:
        json.dump(data, f, indent=1)
    print(f"{len(data['work'])} pieces, {len(data['beforeAfter'])} before and afters")


if __name__ == "__main__":
    assert auto("07-minecraft-100-days-skyblock.png") == ("minecraft", "100 days skyblock")
    assert auto("roblox_tower_of_doom.jpg") == ("roblox", "Tower of doom")
    main()
