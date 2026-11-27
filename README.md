# Portfolio site

Live at **https://iffy13.github.io/scouting/** (after the one time setup below).

## Add a new thumbnail (works from your phone)
1. On GitHub open the `site/work` folder, tap **Add file → Upload files**, pick the image, tap **Commit changes**.
2. Name it like `09-roblox-tower-of-doom.jpg` or `10-minecraft-100-days-skyblock.png`:
   the number sets the order, the first word sets the game filter, the rest becomes the caption.
3. About a minute later it is live.

Before and afters go in `site/before-after` the same way.
For a nicer caption or a format label ("VS duel", "Countdown"), add the file name to `captions.json`.
To remove a piece, delete its file.

## One time setup
Pages is on and serves the gh-pages branch, which the Portfolio site workflow updates. To publish by hand, run
**Actions → Portfolio site → Run workflow** once (or upload any file to `site/`).
