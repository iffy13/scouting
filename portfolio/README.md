# Showcase thumbnails

## Set 2 (lead with these): the winning formats from top Roblox and Minecraft thumbnails

| File | Format | Pitch it to |
|---|---|---|
| roblox_vs_whos_faster | VS duel: split colors, lightning, angry vs smug, boxed question | challenge and duel channels |
| minecraft_hardcore_hearts | game UI story: 1 heart left, Hearts box, scared close-up, monster | hardcore and survival channels |
| roblox_time_left | countdown: top-down panic, props, red timer | timed challenge channels |
| minecraft_max_armor | showcase: sunburst, glowing gear, curved arrow | PvP, armor and mod channels |

`showcase_sheet_v2.jpg` has all four. Render them again with `node shoot2.js` (uses `thumb2.html`):
textured characters, white sticker outlines, pixel icons (skulls, hearts), sweat drops, swirls, arrows, labels.

## Set 1

Made from scratch: real 3D scenes (three.js) with my own blocky characters, rim lights, glow, depth and
outlined titles. Each comes with the "before", a typical small-creator thumbnail of the same scene.

| File | For | Pitch it to |
|---|---|---|
| roblox_dont_fall | Roblox obby / challenge | gameplay channels |
| roblox_secret_base | Roblox story / roleplay | Brookhaven, story channels |
| minecraft_day_100 | Minecraft hardcore / 100 days | survival channels |
| minecraft_server_new_season | Minecraft server key art | server owners |

`showcase_sheet.jpg` is all four on one image, for a first DM or a portfolio header.

## Make more or change one

```
cd portfolio/render
npm install three@0.160.0
python3 -m http.server 8765 &          # serves scene.html
node shoot.js lava,hardcore,secret,server   # writes out/<scene>_after.png and _before.png
```
Edit the scene functions in `scene.html` (camera, pose, colors, words) and run `shoot.js` again.
Needs Playwright with Chromium (`npm install playwright && npx playwright install chromium` on your PC).
