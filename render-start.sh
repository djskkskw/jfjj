#!/bin/sh
# ═══════════════════════════════════════════════════════════════════════════
#  Render entrypoint for the JAFJ manager.
#
#  Render runs Docker web services and injects $PORT; the manager's health
#  server already binds 0.0.0.0:$PORT and answers "/" with 200, which is both
#  the Render health check and what keeps a free instance from sleeping.
#
#  A persistent Render Disk is mounted at /data. Exactly like the Railway
#  layout, the immutable code stays in the image at /opt/jafj while ONLY data
#  lives on the disk — so a redeploy can never run an old manager_82.py / a
#  broken 95.py left behind on the disk.
#
#  This wrapper only supplies the Render-specific defaults; the whole boot +
#  fresh-code + crash-supervision flow is the host-neutral railway-start.sh
#  (kept under that name for backwards compatibility with existing images).
# ═══════════════════════════════════════════════════════════════════════════
set -eu

IMAGE_DIR="${JAFJ_IMAGE_DIR:-/opt/jafj}"

# Render persistent Disk mount point. Override with JAFJ_APP_DIR if you mount
# the disk somewhere else; the shared entrypoint falls back to /data anyway.
export JAFJ_APP_DIR="${JAFJ_APP_DIR:-/data}"

exec sh "$IMAGE_DIR/railway-start.sh" "$@"
