#!/usr/bin/env bash
# Keeps outreach.db between runs by storing it, ENCRYPTED, as a single commit on a branch called "data".
# The repository is public, so the database is never pushed in readable form: it is saved as outreach.db.enc,
# locked with the DB_PASSPHRASE secret (AES-256, openssl). Without that secret the file is unreadable.
#
# Usage:
#   bash ci/data_sync.sh restore                 download and unlock the database
#   bash ci/data_sync.sh save                    lock and upload the database
#   bash ci/data_sync.sh encrypt-file IN OUT     lock any file (used for the PC runner's lead hand-over)
#   bash ci/data_sync.sh decrypt-file IN OUT     unlock it again
#
# Safety: "restore" only starts fresh when the data branch really does not exist. Any other
# failure (network, auth, wrong passphrase) stops the run. "save" refuses to push unless restore succeeded
# in this run, so a failed restore can never overwrite the saved database with an empty one.
# Older versions saved a readable outreach.db. restore still accepts that once; the next save replaces it
# with the encrypted file and the readable one is gone from the branch.
set -euo pipefail

WORK="$(pwd)"
MARKER="$WORK/.data_restored"

need_pass() {
  if [ -z "${DB_PASSPHRASE:-}" ]; then
    echo "DB_PASSPHRASE is not set. Add it under Settings, Secrets and variables, Actions (any long random text)."
    exit 1
  fi
}

lock()   { need_pass; openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:DB_PASSPHRASE -in "$1" -out "$2"; }
unlock() {
  need_pass
  if ! openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:DB_PASSPHRASE -in "$1" -out "$2" 2>/dev/null; then
    echo "Could not unlock $1. DB_PASSPHRASE is wrong or was changed. Stopping so nothing is overwritten."
    rm -f "$2"
    exit 1
  fi
}

case "${1:-}" in
  encrypt-file) lock "$2" "$3"; exit 0 ;;
  decrypt-file) unlock "$2" "$3"; exit 0 ;;
esac

: "${DATA_REMOTE:?DATA_REMOTE is not set}"
TMP="$(mktemp -d)"
cd "$TMP"
git init -q -b data
git remote add origin "$DATA_REMOTE"

retry() {
  local n
  for n in 1 2 3 4; do
    "$@" && return 0
    echo "Attempt $n failed, retrying in $((n * 5))s..."
    sleep $((n * 5))
  done
  return 1
}

case "${1:-}" in
  restore)
    rm -f "$MARKER"
    need_pass
    # ls-remote: 0 = branch exists, 2 = remote answered and branch is missing, anything else = error.
    found=1
    for n in 1 2 3 4; do
      set +e; git ls-remote --exit-code --heads origin data >/dev/null 2>&1; found=$?; set -e
      [ "$found" -eq 0 ] || [ "$found" -eq 2 ] && break
      echo "Could not reach the repository (attempt $n), retrying in $((n * 5))s..."
      sleep $((n * 5))
    done
    if [ "$found" -eq 0 ]; then
      retry git fetch -q --depth 1 origin data || { echo "Could not download the data branch. Stopping so the saved database is not overwritten."; exit 1; }
      if git cat-file -e FETCH_HEAD:outreach.db.enc 2>/dev/null; then
        git checkout -q FETCH_HEAD -- outreach.db.enc
        unlock outreach.db.enc "$WORK/outreach.db"
        echo "Restored and unlocked outreach.db from the data branch."
      elif git cat-file -e FETCH_HEAD:outreach.db 2>/dev/null; then
        git checkout -q FETCH_HEAD -- outreach.db
        cp outreach.db "$WORK/outreach.db"
        echo "Restored an old unencrypted outreach.db. It will be saved encrypted at the end of this run."
      else
        echo "The data branch has no database file. Stopping so nothing is overwritten."
        exit 1
      fi
    elif [ "$found" -eq 2 ]; then
      echo "No saved database yet, starting fresh."
    else
      echo "Could not reach the repository to check for the data branch. Stopping so the saved database is not overwritten."
      exit 1
    fi
    touch "$MARKER"
    ;;
  save)
    if [ ! -f "$MARKER" ]; then
      echo "Restore did not succeed in this run, refusing to save (would overwrite the stored database)."
      exit 1
    fi
    if [ -f "$WORK/outreach.db" ]; then
      lock "$WORK/outreach.db" outreach.db.enc
      git config user.name "autopilot"
      git config user.email "autopilot@users.noreply.github.com"
      git add outreach.db.enc
      # A brand new commit with no history, so no readable copy from older runs stays on the branch.
      git commit -q -m "database (encrypted) $(date -u +%Y-%m-%dT%H:%MZ)"
      retry git push -q -f origin data
      echo "Saved encrypted outreach.db.enc to the data branch."
    else
      echo "No database to save."
    fi
    ;;
  *) echo "Use restore, save, encrypt-file or decrypt-file"; exit 1 ;;
esac
