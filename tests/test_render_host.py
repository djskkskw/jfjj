#!/usr/bin/env python3
"""پشتیبانیِ Render: Blueprint + نگهبانِ «دیسک روی کد» + شناساییِ میزبان.

Railway بسته شده. اینجا سه چیز تضمین می‌شود:
  ۱) render.yaml درست است (worker + docker + disk روی /data، نه /app)
  ۲) railway-start.sh (entrypoint مشترک) اگر ببیند پوشه‌ی داده یک نسخه‌ی
     قابل‌اجرا از کد دارد، داده را به mount اختصاصی می‌برد و هشدار می‌دهد؛
     اگر mount ممکن نباشد رفتارِ قدیمی را با هشدار نگه می‌دارد (بوت نمی‌شکند)
  ۳) manager_82.py با env‌های Render میزبان‌شناس است و روی 0.0.0.0:$PORT
     هلث‌سرویس می‌بندد
"""
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
ROOT = Path(tempfile.gettempdir()) / "jafj_render_host_run"

DRIVER = r"""
import os, sys, time, urllib.request
code_dir, manager = os.environ["JAFJ_CODE_DIR"], sys.argv[1]
sys.argv = [manager]
sys.path.insert(0, code_dir)
import manager_82 as M

print("IMPORTED_FROM", M.__file__, flush=True)
print("HOSTED", M.is_hosted(), flush=True)
print("LOGIN_RETRY", M.login_retry_forever(), flush=True)
print("SELFBOT", M.SELFBOT, flush=True)
print("SELFBOT_ISFILE", os.path.isfile(M.SELFBOT or ""), flush=True)
print("DATA", os.path.abspath(M.BASE_DIR), flush=True)

port = int(os.environ.get("PORT", "0"))
body = ""
for _ in range(40):
    try:
        body = urllib.request.urlopen("http://0.0.0.0:%d/" % port,
                                      timeout=1).read().decode()
        break
    except Exception:
        time.sleep(0.25)
print("HEALTH", repr(body), flush=True)
"""

FAILS = []


def check(cond, label):
    print(("PASS  " if cond else "FAIL  ") + label)
    if not cond:
        FAILS.append(label)
    return bool(cond)


def check_blueprint():
    p = REPO / "render.yaml"
    if not check(p.exists(), "render.yaml در ریشه‌ی ریپو هست"):
        return
    t = p.read_text(encoding="utf-8")
    check(re.search(r"type:\s*worker", t), "نوعِ سرویس worker است")
    check(re.search(r"runtime:\s*docker", t), "runtime روی docker")
    check(re.search(r"dockerfilePath:\s*\./Dockerfile", t),
          "dockerfilePath = ./Dockerfile")
    check(re.search(r"plan:\s*starter", t), "plan: starter")
    check("disk:" in t, "بخشِ disk وجود دارد")
    mounts = re.findall(r"mountPath:\s*(\S+)", t)
    check(mounts == ["/data"], "mountPath دقیقاً /data است (بود %r)" % mounts)
    check(all(mm not in ("/app", "/opt/jafj") for mm in mounts),
          "دیسک هرگز روی مسیرِ کد (/app یا /opt/jafj) مانت نمی‌شود")
    for key, val in (("DATA_DIR", "/data"), ("JAFJ_IMAGE_DIR", "/opt/jafj"),
                     ("JAFJ_APP_DIR", "/data"), ("PORT", "10000")):
        check(re.search(r"key:\s*%s\s*\n\s*value:\s*\"?%s\"?" % (key, val), t),
              "env %s = %s" % (key, val))
    check(re.search(r"key:\s*BOT_TOKEN\s*\n\s*sync:\s*false", t),
          "BOT_TOKEN به‌صورت secret (sync: false)")


def run_entry(image, app, data_mount, env_extra=None, make_code_copy=True,
              writable_mount=True):
    """یک کانتینرِ جعلی می‌سازد و entrypoint واقعی را با JAFJ_SUPERVISE=0 اجرا می‌کند."""
    shutil.rmtree(ROOT, ignore_errors=True)
    image.mkdir(parents=True)
    app.mkdir(parents=True)
    for name in ("manager_82.py", "95.py", "railway-start.sh"):
        shutil.copy2(REPO / name, image / name)
    if make_code_copy:
        (app / "manager_82.py").write_text("print('STALE')\n", encoding="utf-8")
    if writable_mount:
        data_mount.mkdir(parents=True, exist_ok=True)
    else:
        # مسیرِ mount را غیرقابل‌ساخت کن: یک فایل به‌جای پوشه
        data_mount.parent.mkdir(parents=True, exist_ok=True)
        data_mount.write_text("not a dir", encoding="utf-8")

    env = dict(os.environ, JAFJ_IMAGE_DIR=str(image), JAFJ_APP_DIR=str(app),
               JAFJ_DATA_MOUNT=str(data_mount), JAFJ_SUPERVISE="0",
               PYTHON="/bin/true")
    env.pop("DATA_DIR", None)
    for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RENDER",
              "RENDER_SERVICE_NAME"):
        env.pop(k, None)
    if env_extra:
        env.update(env_extra)
    p = subprocess.run(["sh", str(image / "railway-start.sh")], env=env,
                       capture_output=True, text=True, timeout=120)
    return p.stdout + p.stderr, p.returncode


def check_entrypoint():
    image = ROOT / "opt" / "jafj"
    app = ROOT / "appdata"
    mount = ROOT / "mnt" / "data"

    # ۱) پوشه‌ی داده کد دارد + mount ممکن → داده به mount، هشدار، کد از ایمیج
    out, rc = run_entry(image, app, mount)
    check(rc == 0, "۱) بوت با موفقیت تمام شد")
    check("WARNING" in out and "holds a copy of manager_82.py" in out,
          "۱) هشدارِ «دیسک روی کد» داده شد")
    check("data=%s" % mount in out,
          "۱) داده به mount اختصاصی رفت (%s)" % mount)
    check("code=%s" % image in out, "۱) کد از ایمیج اجرا می‌شود")

    # ۲) mount ممکن نیست → همان پوشه‌ی قدیمی با هشدار (بوت نمی‌شکند)
    out, rc = run_entry(image, app, mount, writable_mount=False)
    check(rc == 0, "۲) وقتی mount ممکن نیست، بوت نمی‌شکند")
    check("WARNING" in out, "۲) هشدار داده شد")
    check("data=%s" % app in out, "۲) رفتارِ قدیمی: همان پوشه‌ی داده")

    # ۳) پوشه‌ی داده تمیز → بدون هشدار
    out, rc = run_entry(image, app, mount, make_code_copy=False)
    check(rc == 0 and "WARNING" not in out, "۳) پوشه‌ی تمیز → بدون هشدار")
    check("data=%s" % app in out, "۳) داده همان‌جا می‌ماند")

    # ۴) DATA_DIR صریح همیشه محترم است (ولی هشدار می‌گیرد)
    out, rc = run_entry(image, app, mount, env_extra={"DATA_DIR": str(app)})
    check(rc == 0 and "data=%s" % app in out,
          "۴) DATA_DIR صریح محترم شمرده شد")
    check("NEVER executed" in out, "۴) هشدارِ «آن نسخه اجرا نمی‌شود» داده شد")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def check_manager():
    shutil.rmtree(ROOT, ignore_errors=True)
    image = ROOT / "opt" / "jafj"
    data = ROOT / "data"
    image.mkdir(parents=True)
    data.mkdir(parents=True)
    for name in ("manager_82.py", "95.py", "railway-start.sh"):
        shutil.copy2(REPO / name, image / name)
    driver = ROOT / "driver.py"
    driver.write_text(DRIVER, encoding="utf-8")
    wrapper = ROOT / "python-wrapper.sh"
    wrapper.write_text('#!/bin/sh\nexec "%s" "%s" "$@"\n'
                       % (sys.executable, driver), encoding="utf-8")
    wrapper.chmod(0o755)

    port = str(free_port())
    env = dict(os.environ, JAFJ_IMAGE_DIR=str(image), JAFJ_APP_DIR=str(data),
               JAFJ_CODE_DIR=str(image), DATA_DIR=str(data),
               JAFJ_SUPERVISE="0", PORT=port, PYTHON=str(wrapper),
               RENDER="true", RENDER_SERVICE_NAME="jafj")
    for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "JAFJ_HOSTED",
              "JAFJ_LOGIN_RETRY", "BOT_TOKEN", "API_ID", "API_HASH"):
        env.pop(k, None)
    p = subprocess.run(["sh", str(image / "railway-start.sh")], env=env,
                       capture_output=True, text=True, timeout=180)
    out = p.stdout + p.stderr
    for line in out.splitlines():
        if line.startswith(("IMPORTED_FROM", "HOSTED", "LOGIN_RETRY",
                            "SELFBOT", "DATA", "HEALTH")):
            print(line)
    check("HOSTED True" in out, "با RENDER/RENDER_SERVICE_NAME → is_hosted()")
    check("LOGIN_RETRY True" in out, "login_retry_forever() روی میزبان True")
    check("SELFBOT_ISFILE True" in out, "SELFBOT پیدا شد و موجود است")
    check("HEALTH ''" not in out and "JAFJ OK" in out,
          "هلث‌سرویس روی 0.0.0.0:$PORT جواب می‌دهد")
    check("RENDER_SERVICE_NAME" in (REPO / "manager_82.py").read_text(
        encoding="utf-8"), "کلیدهای Render در HOSTED_ENV_KEYS هستند")


def main():
    print("--- Render support: blueprint + entrypoint guard + host detect ---")
    check_blueprint()
    check_entrypoint()
    check_manager()
    shutil.rmtree(ROOT, ignore_errors=True)
    if FAILS:
        print("FAILED:", len(FAILS))
        for f in FAILS:
            print("  -", f)
        print("ALL: FAIL")
        return False
    print("DONE PASS")
    print("ALL: PASS")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
