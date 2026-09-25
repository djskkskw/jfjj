#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""همگام‌سازی اطلاعات مشتری‌ها با گیت‌هاب (tools/gh_data_sync.py).

سناریوها:
  1) بسته‌ی داده دقیقاً همان فهرست اطلاعات مشتری را می‌گیرد (run.log و … نه)
  2) push→pull دورتی واقعی روی HTTP با Fake Contents API: داده از بین می‌رود،
     از گیت‌هاب برمی‌گردد (حتی ردیف‌های sqlite و سشن‌ها)
  3) بدون تغییر → push جدید نمی‌زند (اثرانگشت)
  4) تلاقی نسخه (409) → تلاش دوباره با sha تازه
  5) پشتیبان نیست (404) → pull بی‌خطر رد می‌شود (بوت اول)
  6) داده‌ی محلی خالی → push از بازنویسیِ پشتیبان موجود خودداری می‌کند
  7) loop با SIGTERM → «ذخیره‌ی پایانی» و خروج تمیز
  8) سیم‌کشیِ start script / render.yaml / Dockerfile + stdlib بودنِ ابزار
"""
import base64
import hashlib
import http.server
import importlib.util
import json
import os
import re
import shutil
import signal
import sqlite3
import socket
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
import io
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
ROOT = Path(tempfile.gettempdir()) / "jafj_gh_data_sync_run"

FAILS = []


def check(cond, label):
    print(("PASS  " if cond else "FAIL  ") + label)
    if not cond:
        FAILS.append(label)
    return bool(cond)


def load_sync():
    spec = importlib.util.spec_from_file_location(
        "mgh", str(REPO / "tools" / "gh_data_sync.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Fake GitHub Contents API (HTTP واقعی روی 127.0.0.1) ──────────────────────

class FakeGH(http.server.BaseHTTPRequestHandler):
    store = {}          # path -> (sha, content bytes)
    put_attempts = 0
    force_conflict = 0

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _path(self):
        p = self.path.split("?", 1)[0]
        marker = "/contents/"
        i = p.find(marker)
        return p[i + len(marker):] if i >= 0 else ""

    def do_GET(self):
        path = self._path()
        if path in FakeGH.store:
            sha, content = FakeGH.store[path]
            self._send(200, {
                "content": base64.b64encode(content).decode("ascii"),
                "encoding": "base64", "sha": sha, "path": path})
        else:
            self._send(404, {"message": "Not Found"})

    def do_PUT(self):
        FakeGH.put_attempts += 1
        path = self._path()
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        content = base64.b64decode(body.get("content", ""))
        if FakeGH.force_conflict > 0:
            FakeGH.force_conflict -= 1
            self._send(409, {"message": "Conflict (forced)"})
            return
        cur = FakeGH.store.get(path)
        if cur is not None and body.get("sha") != cur[0]:
            self._send(409, {"message": "does not match"})
            return
        if cur is None and body.get("sha"):
            self._send(409, {"message": "does not match (missing)"})
            return
        sha = hashlib.sha1(content).hexdigest()
        FakeGH.store[path] = (sha, content)
        self._send(201 if cur is None else 200, {"content": {"sha": sha}})

    def do_DELETE(self):
        path = self._path()
        FakeGH.store.pop(path, None)
        self._send(200, {})


class FakeServer:
    def __init__(self):
        FakeGH.store = {}
        FakeGH.put_attempts = 0
        FakeGH.force_conflict = 0
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeGH)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def make_data_dir(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    for name, content in (("manager_config.json", '{"bot_token": "t"}'),
                          ("manager_bot.string", "SESSIONDATA"),
                          ("jafj_ai.json", "{}"),
                          (".jafj_deploy_id", "abc123")):
        (root / name).write_text(content, encoding="utf-8")
    con = sqlite3.connect(str(root / "manager.db"))
    con.execute("CREATE TABLE customers(x INTEGER)")
    con.executemany("INSERT INTO customers(x) VALUES (?)", [(1,), (2,)])
    con.commit()
    con.close()
    con = sqlite3.connect(str(root / "shop.db"))
    con.execute("CREATE TABLE plans(x INTEGER)")
    con.execute("INSERT INTO plans(x) VALUES (9)")
    con.commit()
    con.close()
    c7 = root / "clients" / "7"
    c7.mkdir(parents=True, exist_ok=True)
    (c7 / "jafj.session").write_bytes(b"\x00SESSION\x01")
    for name, content in (("jafj_creds.json", '{"dc_id": 2}'),
                          ("jafj_ai.json", "{}"),
                          ("jafj_limits.json", "{}"),
                          ("jafj_settings.json", "{}"),
                          ("jafj_status.json", "{}")):
        (c7 / name).write_text(content, encoding="utf-8")
    (c7 / "run.log").write_text("noise", encoding="utf-8")
    (c7 / "jafj.session-journal").write_bytes(b"tmp")
    (c7 / "debug.log").write_text("noise2", encoding="utf-8")


EXPECTED = {
    "manager.db", "shop.db", "manager_config.json", "manager_bot.string",
    "jafj_ai.json", ".jafj_deploy_id",
    "clients/7/jafj.session", "clients/7/jafj_creds.json",
    "clients/7/jafj_ai.json", "clients/7/jafj_limits.json",
    "clients/7/jafj_settings.json", "clients/7/jafj_status.json",
}

BUNDLE_PATH = "data/customer_data.zip"


def env_for(data: Path, port, **extra):
    env = dict(os.environ,
               DATA_DIR=str(data),
               DATA_GITHUB_TOKEN="test-token",
               DATA_GITHUB_REPO="djskkskw/jfjj-data",
               DATA_GITHUB_PATH=BUNDLE_PATH,
               DATA_GITHUB_BRANCH="main",
               DATA_GITHUB_API="http://127.0.0.1:%d" % port)
    env.update(extra)
    return env


def run_cli(data: Path, port, cmd, **extra):
    return subprocess.run(
        [sys.executable, str(REPO / "tools" / "gh_data_sync.py"), cmd],
        env=env_for(data, port, **extra), capture_output=True, text=True,
        timeout=120)


def stored_zip():
    return FakeGH.store[BUNDLE_PATH][1]


def scenario_bundle_inventory(mod):
    print("--- 1: بسته‌ی داده فقط اطلاعات مشتری را می‌گیرد ---")
    data = ROOT / "s1"
    shutil.rmtree(data, ignore_errors=True)
    make_data_dir(data)
    old = os.environ.get("DATA_DIR")
    os.environ["DATA_DIR"] = str(data)
    try:
        blob, manifest = mod.build_bundle()
        names = {r["path"] for r in manifest["files"]}
        check(names == EXPECTED,
              "فهرست دقیق فایل‌ها (بود %r)" % sorted(names ^ EXPECTED))
        check("clients/7/run.log" not in names, "run.log بیرون می‌ماند")
        check("clients/7/jafj.session-journal" not in names,
              "فایل‌های journal بیرون می‌مانند")
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            znames = set(zf.namelist())
            m = json.loads(zf.read("manifest.json").decode("utf-8"))
        check(EXPECTED <= znames, "فایل‌ها داخل zip هستند")
        check("manifest.json" in znames, "manifest داخل zip است")
        check(m.get("format") == 1 and m.get("fingerprint"), "manifest قالب/اثرانگشت دارد")
        fp1 = m["fingerprint"]
        (data / "manager_config.json").write_text('{"bot_token": "t2"}', encoding="utf-8")
        blob2, manifest2 = mod.build_bundle()
        check(manifest2["fingerprint"] != fp1, "با تغییر داده، اثرانگشت عوض می‌شود")
        (data / "manager_config.json").write_text('{"bot_token": "t2x"}', encoding="utf-8")
        b3, m3 = mod.build_bundle()
        check(m3["fingerprint"] != manifest2["fingerprint"], "اثرانگشت به محتوا حساس است")
    finally:
        if old is None:
            os.environ.pop("DATA_DIR", None)
        else:
            os.environ["DATA_DIR"] = old


def scenario_roundtrip(port):
    print("--- 2: push → wipe → pull (دورتی واقعی روی HTTP) ---")
    data = ROOT / "s2"
    shutil.rmtree(data, ignore_errors=True)
    make_data_dir(data)
    FakeGH.store = {}
    FakeGH.put_attempts = 0
    r = run_cli(data, port, "push")
    check(r.returncode == 0 and "ذخیره شد" in r.stdout, "push سبز شد")
    check(FakeGH.put_attempts == 1, "دقیقاً یک PUT")
    check(BUNDLE_PATH in FakeGH.store, "فایل zip در «گیت‌هاب» هست")
    shutil.rmtree(data)
    data.mkdir(parents=True)
    r = run_cli(data, port, "pull")
    check(r.returncode == 0 and "بازیابی شد" in r.stdout, "pull سبز شد")
    check((data / "manager_bot.string").read_text(encoding="utf-8") == "SESSIONDATA",
          "نشستِ manager برگشت")
    check((data / "clients" / "7" / "jafj.session").read_bytes() == b"\x00SESSION\x01",
          "سشنِ مشتری برگشت")
    check(not (data / "clients" / "7" / "run.log").exists(), "run.log بازنمی‌گردد")
    con = sqlite3.connect(str(data / "manager.db"))
    rows = [x[0] for x in con.execute("SELECT x FROM customers ORDER BY x")]
    con.close()
    check(rows == [1, 2], "ردیف‌های sqlite سالم برگشتند (بود %r)" % rows)
    mode = (data / "clients" / "7" / "jafj.session").stat().st_mode & 0o777
    check(mode == 0o600, "فایل‌های حساس با مجوز ۶۰۰ نوشته می‌شوند (بود %o)" % mode)
    # اثرانگشت: push دوباره بدون تغییر نباید PUT تازه بزند
    n0 = FakeGH.put_attempts
    r = run_cli(data, port, "push")
    check(r.returncode == 0 and "بدون تغییر" in r.stdout, "push بدون تغییر → بدون ذخیره‌ی جدید")
    check(FakeGH.put_attempts == n0, "PUT تازه‌ای زده نشد")
    (data / "manager_config.json").write_text('{"bot_token": "new"}', encoding="utf-8")
    n1 = FakeGH.put_attempts
    r = run_cli(data, port, "push")
    check(r.returncode == 0 and FakeGH.put_attempts == n1 + 1,
          "با تغییر داده، ذخیره‌ی جدید انجام می‌شود")


def scenario_conflict_retry(port):
    print("--- 3: تلاقی 409 → تلاش دوباره با sha تازه ---")
    data = ROOT / "s3"
    shutil.rmtree(data, ignore_errors=True)
    make_data_dir(data)
    FakeGH.store = {}
    FakeGH.put_attempts = 0
    r = run_cli(data, port, "push")
    check(r.returncode == 0, "push اولیه")
    (data / "jafj_ai.json").write_text('{"k": 1}', encoding="utf-8")
    FakeGH.force_conflict = 1
    n0 = FakeGH.put_attempts
    r = run_cli(data, port, "push")
    check(r.returncode == 0 and "تلاقی" in r.stdout, "تلاقی گزارش و رفع شد")
    check(FakeGH.put_attempts == n0 + 2, "اولی 409، دومی موفق (بود %d تلاش)"
          % (FakeGH.put_attempts - n0))
    with zipfile.ZipFile(io.BytesIO(stored_zip())) as zf:
        m = json.loads(zf.read("manifest.json").decode("utf-8"))
    check(any(f["path"] == "jafj_ai.json" for f in m["files"]), "نسخه‌ی تازه نشست")


def scenario_fresh_and_protect(port):
    print("--- 4: بوت اول (404) و محافظت از پشتیبان موجود ---")
    data = ROOT / "s4"
    shutil.rmtree(data, ignore_errors=True)
    make_data_dir(data)
    FakeGH.store = {}
    FakeGH.put_attempts = 0
    r = run_cli(data, port, "pull")
    check(r.returncode == 0 and "هنوز پشتیبانی" in r.stdout, "pull بی‌پشتیبان → بی‌خطر رد شد")
    check((data / "manager_bot.string").exists(), "داده‌ی محلی دست نخورد")
    # push کن، بعد داده‌ی محلی را خالی کن → push نباید پشتیبان را با بسته‌ی خالی عوض کند
    r = run_cli(data, port, "push")
    check(r.returncode == 0, "push اولیه")
    keep = stored_zip()
    shutil.rmtree(data)
    data.mkdir(parents=True)
    r = run_cli(data, port, "push")
    check(r.returncode != 0 and "دست نخورد" in r.stdout,
          "داده‌ی خالی → بازنویسیِ پشتیبان رد شد")
    check(stored_zip() == keep, "پشتیبانِ گیت‌هاب عوض نشد")


def scenario_loop_sigterm(port):
    print("--- 5: loop + SIGTERM → ذخیره‌ی پایانی و خروج تمیز ---")
    data = ROOT / "s5"
    shutil.rmtree(data, ignore_errors=True)
    make_data_dir(data)
    FakeGH.store = {}
    FakeGH.put_attempts = 0
    p = subprocess.Popen(
        [sys.executable, str(REPO / "tools" / "gh_data_sync.py"), "loop"],
        env=env_for(data, port, DATA_GITHUB_INTERVAL_MIN="0.02"),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    ok = False
    for _ in range(150):
        if FakeGH.put_attempts >= 1:
            ok = True
            break
        time.sleep(0.1)
    check(ok, "push اولیه‌ی loop انجام شد")
    p.send_signal(signal.SIGTERM)
    try:
        out, _ = p.communicate(timeout=25)
    except subprocess.TimeoutExpired:
        p.kill()
        out, _ = p.communicate()
    check(p.returncode == 0, "خروج تمیز بعد از SIGTERM (rc=%s)" % p.returncode)
    check("ذخیره‌ی پایانی" in out, "«ذخیره‌ی پایانی» انجام شد")
    check("loop تمام شد" in out, "loop خودش را جمع کرد")


def scenario_wiring():
    print("--- 6: سیم‌کشی start script / render.yaml / Dockerfile ---")
    rs = (REPO / "railway-start.sh").read_text(encoding="utf-8")
    check("gh_data_sync" in rs, "railway-start.sh ابزار را صدا می‌زند")
    i_pull = rs.find('"$PY" "$SYNC" pull')
    i_run = rs.find('exec "$PY" "$MANAGER"')
    check(0 < i_pull < i_run, "بازیابی قبل از استارتِ manager است")
    check('"$PY" "$SYNC" loop &' in rs, "ذخیره‌ی دوره‌ای در پس‌زمینه")
    check('if [ -n "${DATA_GITHUB_TOKEN:-}" ]' in rs,
          "بدون توکن، هیچ اتفاقی نمی‌افتد (اختیاری)")
    check("stop_sync" in rs and "stop_sync\n        exit \"$code\"" in rs,
          "هنگام خاموشی، ذخیره‌ی پایانی فرصت اجرا می‌گیرد")
    ry = (REPO / "render.yaml").read_text(encoding="utf-8")
    check(re.search(r"key:\s*DATA_GITHUB_TOKEN\s*\n\s*sync:\s*false", ry),
          "DATA_GITHUB_TOKEN در render.yaml به‌صورت secret (sync: false)")
    dk = (REPO / "Dockerfile").read_text(encoding="utf-8")
    check("COPY tools/ /opt/jafj/tools/" in dk, "ابزار داخل ایمیج می‌رود")
    src = (REPO / "tools" / "gh_data_sync.py").read_text(encoding="utf-8")
    imports = re.findall(r"^\s*(?:import|from)\s+([A-Za-z_][\w.]*)", src, re.M)
    banned = [m for m in imports if m.split(".")[0]
              not in {"base64", "hashlib", "io", "json", "os", "shutil", "signal",
                      "sqlite3", "sys", "tempfile", "time", "urllib", "zipfile",
                      "__future__"}]
    check("urllib.request" in src and not banned,
          "ابزار فقط stdlib است (importهای بیگانه: %r)" % banned)
    for tok in ("manager.db", "shop.db", "manager_config.json", "manager_bot.string",
                "jafj_ai.json", ".jafj_deploy_id", "clients"):
        check(tok in src, "فهرست بسته شامل %s است" % tok)


def main():
    print("--- GitHub data sync: پشتیبان/بازیابی اطلاعات مشتری‌ها ---")
    shutil.rmtree(ROOT, ignore_errors=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    mod = load_sync()
    server = FakeServer()
    try:
        scenario_bundle_inventory(mod)
        scenario_roundtrip(server.port)
        scenario_conflict_retry(server.port)
        scenario_fresh_and_protect(server.port)
        scenario_loop_sigterm(server.port)
    finally:
        server.close()
    scenario_wiring()
    shutil.rmtree(ROOT, ignore_errors=True)
    if FAILS:
        print("FAILED:", len(FAILS))
        for f in FAILS:
            print("  -", f)
        print("ALL: FAIL")
        return False
    print("ALL: PASS")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
