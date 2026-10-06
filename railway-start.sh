#!/bin/sh
# ═══════════════════════════════════════════════════════════════════════════
#  Railway entrypoint for the JAFJ manager.
#
#  Two failure modes this script exists to prevent:
#
#  1) STALE CODE.  A Railway Volume mounted at /app hides everything the image
#     put in /app and keeps whatever the Volume already held. The container
#     then boots the OLD manager_82.py from the Volume on every redeploy, so a
#     fix never arrives and each self start still fails with
#     "به‌روزرسانی فایل سلف نشد: فایل 95.py پیدا نشد".
#     /opt/jafj is part of the image and cannot be shadowed by a Volume, so the
#     code is ALWAYS executed from there; the Volume only stores data.
#
#  2) CRASH LOOP.  Every manager exit used to exit the container, Railway
#     restarted it, and the same failure (Telegram login, FloodWait, leftover
#     lock file, empty Volume) repeated forever. The manager is supervised
#     here now: it is restarted in place, and only repeated instant crashes are
#     handed back to Railway's own restart policy.
#
#  3) HEALTH CHECK. Railway needs 0.0.0.0:$PORT to answer quickly, even while
#     the manager is pulling GitHub data or restarting after a crash. This
#     script now starts a tiny health server immediately, before anything else.
# ═══════════════════════════════════════════════════════════════════════════
set -eu

IMAGE_DIR="${JAFJ_IMAGE_DIR:-/opt/jafj}"     # immutable, inside the image
APP_DIR="${JAFJ_APP_DIR:-/app}"              # usually where the Volume is
MANAGER_NAME="manager_82.py"
SELF_NAME="95.py"

log() { echo "SELFBOOT: $*" >&2; }

# آیا این پوشه‌ی داده، یک نسخه‌ی قابل‌اجرا از کد را نگه داشته است؟
# (دیسک/Volume مانت‌شده روی مسیرِ کد = هر دیپلوی بی‌اثر)
_code_shadow() {
    _d="$1"
    [ -n "$_d" ] || return 1
    [ -f "$_d/$MANAGER_NAME" ] || return 1
    [ "$_d" = "$IMAGE_DIR" ] && return 1
    [ -f "$IMAGE_DIR/$MANAGER_NAME" ] || return 1
    return 0
}

pick_python() {
    if [ -n "${PYTHON:-}" ] && command -v "$PYTHON" >/dev/null 2>&1; then
        echo "$PYTHON"
        return
    fi
    for c in python3 python; do
        if command -v "$c" >/dev/null 2>&1; then
            echo "$c"
            return
        fi
    done
    echo python3
}
PY="$(pick_python)"

# ── 0) Immediate health server for Railway/Render ──────────────────────────
# Railway injects $PORT and expects 0.0.0.0:$PORT to respond within seconds.
# Without this, a slow GitHub pull or a manager restart window makes Railway
# mark the deployment as failed, even though the manager itself also starts a
# health server in a thread.
PORT="${PORT:-8080}"
export PORT

HEALTH_PID=0
start_health() {
    # A minimal HTTP server that answers 200 on any path.
    # It stays alive for the whole container lifetime, so Railway's healthcheck
    # never sees a closed port during manager restarts.
    # Logs go to stderr to avoid contending with manager's stdout pipe.
    "$PY" -u <<'PYEOF' 2>&1 &
import os, sys, time
import http.server, socketserver

port = int(os.environ.get("PORT", "8080"))

def slog(msg):
    print(f"SELFBOOT: {msg}", file=sys.stderr, flush=True)

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Railway healthcheck can use / , /healthz , /health etc.
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "8")
        self.end_headers()
        try:
            self.wfile.write(b"JAFJ OK\n")
        except Exception:
            pass
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "8")
        self.end_headers()
    def log_message(self, *a):
        pass

class ReusableTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 128

# Try a few times; if manager's own health server already bound, this will
# fail and we exit gracefully — manager's server will handle it.
for attempt in range(10):
    try:
        with ReusableTCPServer(("0.0.0.0", port), Handler) as httpd:
            slog(f"health on 0.0.0.0:{port} (entrypoint) pid={os.getpid()}")
            httpd.serve_forever()
        break
    except OSError as e:
        # Address already in use -> another health server is already running (manager's)
        if "Address already in use" in str(e) or "already" in str(e).lower():
            slog(f"health port {port} already in use — another server is handling it")
            break
        slog(f"health bind failed ({e}) attempt {attempt+1}/10")
        time.sleep(1)
    except Exception as e:
        slog(f"health error {e}")
        time.sleep(1)

PYEOF
    HEALTH_PID=$!
    log "health server started pid=$HEALTH_PID port=$PORT"
}

stop_health() {
    if [ "$HEALTH_PID" -gt 0 ]; then
        kill -TERM "$HEALTH_PID" 2>/dev/null || true
        _i=0
        while [ "$_i" -lt 3 ] && kill -0 "$HEALTH_PID" 2>/dev/null; do
            sleep 1
            _i=$((_i + 1))
        done
        kill -KILL "$HEALTH_PID" 2>/dev/null || true
        HEALTH_PID=0
    fi
}

start_health

# ── 1) where does the data live? (Volume wins, image dir is a last resort) ──
if [ -z "${DATA_DIR:-}" ]; then
    if [ -d "$APP_DIR" ] && [ -w "$APP_DIR" ] && ! _code_shadow "$APP_DIR"; then
        DATA_DIR="$APP_DIR"
    else
        if [ -d "$APP_DIR" ] && _code_shadow "$APP_DIR"; then
            log "WARNING: $APP_DIR holds a copy of $MANAGER_NAME — a disk mounted over the code makes every deploy look useless; prefer DATA_DIR=/data"
        fi
        DATA_DIR="${JAFJ_DATA_MOUNT:-/data}"
        if ! mkdir -p "$DATA_DIR" 2>/dev/null || [ ! -w "$DATA_DIR" ]; then
            if [ -d "$APP_DIR" ] && [ -w "$APP_DIR" ]; then
                DATA_DIR="$APP_DIR"
            else
                DATA_DIR="$IMAGE_DIR"
            fi
        fi
    fi
elif _code_shadow "${DATA_DIR:-}"; then
    log "WARNING: DATA_DIR=$DATA_DIR holds a copy of $MANAGER_NAME — that copy is NEVER executed. If redeploys look useless, move the disk: DATA_DIR=/data"
fi
# manager_82.py resolves DATA_DIR against cwd; make it absolute so a relative
# value keeps meaning the same place it did when the code ran from /app.
mkdir -p "$DATA_DIR" 2>/dev/null || true
_abs="$(cd "$DATA_DIR" 2>/dev/null && pwd)" && DATA_DIR="$_abs"
export DATA_DIR

# ── 2) the code always comes from the image ──────────────────────────────────
MANAGER="$IMAGE_DIR/$MANAGER_NAME"
SELF="$IMAGE_DIR/$SELF_NAME"
export JAFJ_SELFBOT_REF="${JAFJ_SELFBOT_REF:-$SELF}"

if [ ! -f "$MANAGER" ]; then
    # Old image without /opt/jafj: fall back to a surviving copy instead of
    # dying in a restart loop.
    if [ -f "$DATA_DIR/$MANAGER_NAME" ]; then
        MANAGER="$DATA_DIR/$MANAGER_NAME"
        log "WARNING: $IMAGE_DIR/$MANAGER_NAME missing — running the copy in $DATA_DIR (rebuild the image)"
    else
        echo "ERROR: no $MANAGER_NAME in $IMAGE_DIR or $DATA_DIR — image is broken or too old, redeploy." >&2
        stop_health
        exit 1
    fi
fi
if [ ! -s "$SELF" ]; then
    log "WARNING: $SELF is missing from the image — self bots cannot start until the image is rebuilt"
fi
# A stale copy in the Volume is not used; say so, because that is exactly what
# made previous redeploys look like they did nothing.
if [ "$DATA_DIR" != "$IMAGE_DIR" ] && [ -f "$DATA_DIR/$MANAGER_NAME" ] \
        && ! cmp -s "$MANAGER" "$DATA_DIR/$MANAGER_NAME" 2>/dev/null; then
    log "note: $DATA_DIR/$MANAGER_NAME differs from the image copy and is NOT executed"
fi

log "code=$IMAGE_DIR data=$DATA_DIR python=$PY self=$([ -s "$SELF" ] && echo ok || echo MISSING) port=$PORT"

# ── 2.5) GitHub data sync: اطلاعات مشتری‌ها از/به گیت‌هاب ────────────────────
# اگر DATA_GITHUB_TOKEN تنظیم نشده باشد، هیچ اتفاقی نمی‌افتد (اختیاری است).
SYNC="$IMAGE_DIR/tools/gh_data_sync.py"
SYNC_PID=0
stop_sync() {
    if [ "$SYNC_PID" -gt 0 ]; then
        kill -TERM "$SYNC_PID" 2>/dev/null || true
        _i=0
        while [ "$_i" -lt 5 ] && kill -0 "$SYNC_PID" 2>/dev/null; do
            sleep 1
            _i=$((_i + 1))
        done
        kill -KILL "$SYNC_PID" 2>/dev/null || true
        SYNC_PID=0
    fi
}
if [ -n "${DATA_GITHUB_TOKEN:-}" ] && [ -f "$SYNC" ]; then
    # قبل از بوت: اطلاعات را از ریپوی گیت‌هاب برگردان (دیپلوی → wipe → بازیابی)
    if "$PY" "$SYNC" pull; then
        log "gh_data_sync: بازیابی از گیت‌هاب انجام شد"
    else
        log "WARNING: gh_data_sync pull ناموفق بود — با داده‌های فعلی ادامه می‌دهیم"
    fi
    # ذخیره‌ی دوره‌ای + ذخیره‌ی پایانی هنگام خاموشی
    "$PY" "$SYNC" loop &
    SYNC_PID=$!
    log "gh_data_sync: ذخیره‌ی دوره‌یی شروع شد (pid=$SYNC_PID)"
fi

# ── 3) run it ───────────────────────────────────────────────────────────────
if [ "${JAFJ_SUPERVISE:-1}" = "0" ]; then
    cd "$DATA_DIR" 2>/dev/null || true
    # In non-supervised mode, keep entrypoint health server alive in background
    # and exec manager. The health server becomes child of init after exec.
    exec "$PY" "$MANAGER"
fi

CHILD=0
STOPPING=0
forward() {
    STOPPING=1
    if [ "$CHILD" -gt 0 ]; then
        kill -TERM "$CHILD" 2>/dev/null || true
    fi
    return 0
}
trap forward TERM INT

crashes=0
MAX_CRASHES="${JAFJ_MAX_CRASHES:-5}"      # پشت‌سرهم → تحویل به Railway
NAP_BASE="${JAFJ_NAP_BASE:-5}"            # ثانیه، هر کرش ۵ تا بیشتر
CRASH_WINDOW="${JAFJ_CRASH_WINDOW:-20}"   # کمتر از این = کرش سریع
while :; do
    cd "$DATA_DIR" 2>/dev/null || true
    "$PY" "$MANAGER" &
    CHILD=$!
    started=$(date +%s)
    set +e
    wait "$CHILD"
    code=$?
    # a trapped signal interrupts wait; keep waiting while the child lives
    while [ "$code" -gt 128 ] && kill -0 "$CHILD" 2>/dev/null; do
        wait "$CHILD"
        code=$?
    done
    set -e
    CHILD=0

    if [ "$STOPPING" = 1 ]; then
        stop_sync
        stop_health
        exit "$code"
    fi
    if [ "$code" = 0 ]; then
        log "manager exited cleanly"
        stop_sync
        stop_health
        exit 0
    fi

    ran=$(( $(date +%s) - started ))
    if [ "$ran" -lt "$CRASH_WINDOW" ]; then
        crashes=$((crashes + 1))
    else
        crashes=0
    fi
    if [ "$crashes" -ge "$MAX_CRASHES" ]; then
        log "manager crashed $crashes times in a row — giving up so Railway reports it"
        stop_sync
        stop_health
        exit "$code"
    fi
    nap=$(( NAP_BASE * (crashes + 1) ))
    if [ "$nap" -gt 60 ]; then
        nap=60
    fi
    log "manager exited with code $code after ${ran}s — restarting in ${nap}s (health still on :$PORT)"
    if [ "$nap" -gt 0 ]; then
        sleep "$nap"
    fi
done
