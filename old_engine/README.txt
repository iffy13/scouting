RETIRED OLD ENGINE - do not run these.

These files are the old "autonomous" outreach engine. It rotated sends across many
Gmail accounts, aimed for up to 250 emails a day, used fake "Re:" subject lines and
emailed EU countries without consent. They were moved here on 11 Oct 2026 and no
longer run: their imports point at files that now live one folder up, so they fail
if you start them from here.

Use instead:
  RUN_SCOUT.bat / SCOUT_MENU.bat       find and score leads (never sends)
  python outreach.py preview|approve   review leads and messages
  python send_paced.py --service ...   send approved leads, one mailbox, paced, capped
  RUN_BOOK_OUTREACH.bat                author outreach, now one mailbox and capped

Kept only for reference. Safe to delete.
