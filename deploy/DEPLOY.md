# Run the autopilot 24/7 on a small server

Once this is set up, scouting, sending, the follow up and Telegram alerts keep running when your PC is off. You still get every alert on your phone.

## What you need (about $5 a month)
A small Linux server. **My pick: Hetzner Cloud CX22** (about 4 EUR a month). DigitalOcean's $6 droplet is fine too. Choose Ubuntu 24.04. The location doesn't matter.

## Do this before deploying: stop your Gmail logins from expiring
If your Google Cloud OAuth app is still in **Testing** mode, Google expires the Gmail logins after 7 days, and sending silently stops. To fix it:
Google Cloud Console -> APIs & Services -> OAuth consent screen -> **Publish app** (set it to "In production").
You don't need Google verification for your own accounts. You'll just see the "unverified app" screen once per account. Then reconnect each mailbox once on your PC with `python outreach.py connect --service ...`.

## Steps
1. On your PC, check the autopilot works: `python autopilot_local.py --dry-run`, then close it.
2. Create the server and copy its IP address.
3. Upload the scouting folder from PowerShell, without the Windows `.venv`:
   ```
   scp -r C:\Users\USER\Downloads\scouting root@SERVER_IP:/opt/scouting
   ssh root@SERVER_IP "rm -rf /opt/scouting/.venv /opt/scouting/__pycache__"
   ```
4. Install:
   ```
   ssh root@SERVER_IP
   cd /opt/scouting && bash deploy/setup_server.sh
   ```
5. Check it without sending: run the two commands the script prints (`--dry-run` and `outreach.py check`). Both mailboxes should say CONFIRMED.
6. **Go live:** `systemctl enable --now scouting-autopilot`. You'll get "Autopilot started" on Telegram.
7. **Stop running it on your PC.** Two copies would double-send.

## Everyday use
- Status: on Telegram (daily summary), or `journalctl -u scouting-autopilot -f`
- Pause: `systemctl stop scouting-autopilot`. Resume: `systemctl start scouting-autopilot`
- After changing a file on your PC, upload that file again with `scp`, then run `systemctl restart scouting-autopilot`

## Keep in mind
The server holds your Gmail logins and Telegram token. Use a strong root password or an SSH key, and don't share access.
