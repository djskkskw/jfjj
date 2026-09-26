#!/usr/bin/env python3
"""بک‌آپ واقعاً گرفته شود — رگرسیون «بک‌آپ نمی‌گیره».

سناریوی گزارش‌شده: بعد از دیپلوی پیام «پشتیبانی پیدا نشد» می‌آید، چون قبلاً
هیچ فایلی به تلگرام نرسیده. این تست چهار علت را روی کد واقعی می‌سنجد:

  1) run.log (رشد بی‌حد) داخل zip نمی‌رود و ارسال به‌خاطر حجم رد نمی‌شود.
  2) اگر ارسال به مقصد اول خطا بدهد، فایل به پیوی مدیر بعدی می‌رود.
  3) getDialogs برای ربات خطا می‌دهد؛ بازیابی باز هم پیوی مدیر را می‌گردد.
  4) پیام متنیِ بی‌فایل با نشانهٔ JAFJBACKUP1 جلوی ساختِ فایل را نمی‌گیرد.
  5) `.backup` / `.restore` و zipی که خودِ مدیر می‌فرستد پذیرفته می‌شوند.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

ROOT = os.path.join(tempfile.gettempdir(), "jafj_backup_taken_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")
STORE = os.path.join(ROOT, "store")
SRC = os.environ.get("REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAKE_INIT = textwrap.dedent('''
import os, shutil

BOT_ID = 111
CHATS = {}
FAIL_SEND = set()
DIALOGS_FAIL = [False]
_next_id = [1000]


def _key(target):
    return str(target).strip().lower().lstrip("@")


class FakeDoc:
    def __init__(self, name="backup.zip"):
        self.name = name
        self.mime_type = "application/zip"


class FakeMsg:
    def __init__(self, mid, chat, caption="", sender_id=BOT_ID, fpath=None, media=None):
        self.id = mid
        self.chat_id = chat
        self.caption = caption or ""
        self.text = caption or ""
        self.message = caption or ""
        self.sender_id = sender_id
        self._fpath = fpath
        self.document = media
        self.media = media
        self.file = media
        self.edits = 0

    async def download_media(self, file=None, **kw):
        return await TelegramClient(None, 1, "h").download_media(self, file=file)


class U:
    username = "fakebot"
    id = BOT_ID


class TelegramClient:
    def __init__(self, session, api_id, api_hash, **kw):
        pass

    async def get_me(self):
        return U()

    async def get_entity(self, x):
        class E:
            username = None
        return E()

    async def get_dialogs(self, limit=None):
        if DIALOGS_FAIL[0]:
            raise RuntimeError("BotMethodInvalidError: getDialogs")
        return []

    def iter_dialogs(self, limit=None):
        async def _gen():
            if DIALOGS_FAIL[0]:
                raise RuntimeError("BotMethodInvalidError: getDialogs")
            return
            yield
        return _gen()

    def iter_messages(self, target, limit=50, **kw):
        async def _gen():
            for m in list(CHATS.get(_key(target), []))[:limit]:
                yield m
        return _gen()

    async def send_message(self, *a, **k):
        class R:
            id = 1
        return R()

    async def send_file(self, target, fpath, caption=None, **kw):
        if _key(target) in FAIL_SEND:
            raise RuntimeError("FilePartsInvalid: too large for bot")
        _next_id[0] += 1
        mid = _next_id[0]
        os.makedirs(os.environ["FAKE_BACKUP_DIR"], exist_ok=True)
        dst = os.path.join(os.environ["FAKE_BACKUP_DIR"], f"msg_{mid}.zip")
        shutil.copy2(str(fpath), dst)
        msg = FakeMsg(mid, _key(target), caption=caption, fpath=dst, media=FakeDoc())
        CHATS.setdefault(_key(target), []).insert(0, msg)
        return msg

    async def edit_message(self, target, message=None, text=None, *a, file=None, **kw):
        for m in CHATS.get(_key(target), []):
            if m.id == message:
                m.caption = text or ""
                m.edits += 1
                if file:
                    dst = os.path.join(os.environ["FAKE_BACKUP_DIR"], f"msg_{m.id}.zip")
                    shutil.copy2(str(file), dst)
                    m._fpath = dst
                    m.document = FakeDoc()
                    m.media = m.document
                return m
        raise RuntimeError("message not found")

    async def delete_messages(self, target, ids, **kw):
        ids = set(ids or ())
        k = _key(target)
        CHATS[k] = [m for m in CHATS.get(k, []) if m.id not in ids]

    async def download_media(self, msg, file=None, **kw):
        src = getattr(msg, "_fpath", None)
        if not src or not os.path.isfile(str(src)):
            raise RuntimeError("no file")
        if file:
            shutil.copy2(str(src), str(file))
            return str(file)
        return str(src)
''')

FAKE_SESS = textwrap.dedent('''
class StringSession:
    def __init__(self, s=""):
        self._s = s or ""
    def save(self):
        return self._s
class SQLiteSession:
    def __init__(self, *a, **k):
        pass
''')

FAKE_ERR = "class FloodWaitError(Exception):\\n    seconds = 0\\n"

DRIVER = textwrap.dedent('''
import os, sys, asyncio, zipfile, shutil
sys.path.insert(0, os.getcwd())
import manager_82 as M
from telethon import TelegramClient, FakeMsg, FakeDoc, CHATS, FAIL_SEND, DIALOGS_FAIL

results = {}

def check(name, cond, extra=""):
    results[name] = bool(cond)
    print(f"{name} {'PASS' if cond else 'FAIL ' + str(extra)}")

def checkpoint(m):
    for conn in (m.db, m.shop):
        try:
            conn.c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.c.commit()
        except Exception:
            pass

async def main():
    try:
        check("C1_dot_backup", M.command_text(".backup") == "/backup")
        check("C2_dot_restore", M.command_text(".restore") == "/restore")
        check("C3_persian_backup", M.command_text("بک آپ") == "/backup")
        check("C4_sentence_not_command", M.command_text("بک آپ نمیگیره") == "بک آپ نمیگیره")
        check("C5_skip_run_log", M.backup_file_skipped("run.log") and M.backup_file_skipped("x.log"))
        check("C6_keep_session", not M.backup_file_skipped("jafj.session"))

        m = M.Manager()
        m.bot = TelegramClient(None, 1, "h")
        m.cfg["admin_ids"] = [111, 222]
        m.db.add(7, "u", "U", 0)
        m.db.set(7, session="SESSION_" + "Y" * 60, phone="+989120000007",
                 status="active", phone_verified=1, tg_id=7)
        checkpoint(m)
        folder = m.sup.folder(7)
        with open(os.path.join(folder, "run.log"), "w", encoding="utf-8") as f:
            f.write("X" * 200000)
        with open(os.path.join(folder, "jafj_settings.json"), "w", encoding="utf-8") as f:
            f.write('{"ok": true}')
        os.environ["BACKUP_CHAT"] = "111"
        ok, msg = await m.backup_once(force=True)
        zpath = CHATS.get("111", [{}])[0]._fpath if CHATS.get("111") else ""
        names = []
        if zpath and os.path.isfile(zpath):
            with zipfile.ZipFile(zpath) as z:
                names = z.namelist()
        check("S1_backup_sent_without_runlog",
              ok and CHATS.get("111") and not any(n.endswith("run.log") for n in names)
              and "manager.db" in names and any(n.endswith("jafj_settings.json") for n in names),
              f"ok={ok} msg={msg} names={names}")

        # مقصد اول ارسال را رد می‌کند → مدیر دوم فایل را می‌گیرد
        CHATS.clear()
        FAIL_SEND.add("111")
        m.db.log(7, "chg", "x")
        checkpoint(m)
        ok2, msg2 = await m.backup_once(force=True)
        check("S2_fallback_other_admin_when_send_fails",
              ok2 and not CHATS.get("111") and CHATS.get("222")
              and CHATS["222"][0].document is not None,
              f"ok={ok2} msg={msg2} chats={list(CHATS)}")
        FAIL_SEND.clear()

        # getDialogs برای ربات خطا می‌دهد؛ پشتیبان در پیوی مدیر دوم است
        DIALOGS_FAIL[0] = True
        os.environ["BACKUP_CHAT"] = "999"
        # دیسک را خالی نکنیم از نظر تلگرام؛ دیتابیس را خالی می‌کنیم با بوت تازه
        keep = CHATS["222"][0]._fpath
        cap = CHATS["222"][0].caption
        # دادهٔ دیسک را پاک کن تا restore لازم شود
        data = os.environ["DATA_DIR"]
        for name in os.listdir(data):
            p = os.path.join(data, name)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                try:
                    os.remove(p)
                except Exception:
                    pass
        CHATS.clear()
        CHATS["222"] = [FakeMsg(50, "222", caption=cap, fpath=keep, media=FakeDoc())]
        m3 = M.Manager()
        m3.bot = TelegramClient(None, 1, "h")
        m3.cfg["admin_ids"] = [111, 222]
        ok3, msg3 = await m3.restore_from_backup(force=False)
        n3 = 0
        try:
            r = m3.db.x("SELECT COUNT(*) c FROM clients", (), "one")
            n3 = r["c"] if r else 0
        except Exception:
            n3 = -1
        check("S3_restore_admin_chat_without_dialogs",
              ok3 and n3 == 1, f"ok={ok3} msg={msg3} n={n3}")
        DIALOGS_FAIL[0] = False

        # پیام متنیِ بی‌فایل نباید جلوی ارسال فایل را بگیرد
        os.environ["BACKUP_CHAT"] = "111"
        CHATS.clear()
        CHATS["111"] = [FakeMsg(9, "111", caption="JAFJBACKUP1 quote only", media=None)]
        m4 = M.Manager()
        m4.bot = TelegramClient(None, 1, "h")
        m4.cfg["admin_ids"] = [111]
        m4.db.add(8, "v", "V", 0)
        checkpoint(m4)
        ok4, msg4 = await m4.backup_once(force=False)
        files = [x for x in CHATS.get("111", []) if getattr(x, "document", None)]
        check("S4_text_tag_does_not_block_file",
              ok4 and len(files) == 1, f"ok={ok4} msg={msg4} n={len(CHATS.get('111', []))}")

        # zip مدیر ذخیره می‌شود و restore از دیسک پیدایش می‌کند
        src_zip = files[0]._fpath
        incoming = FakeMsg(77, "111", caption="JAFJBACKUP1", sender_id=111,
                           fpath=src_zip, media=FakeDoc("jafj_backup.zip"))

        class Ev:
            sender_id = 111
            message = incoming
            document = incoming.document
            raw_text = "JAFJBACKUP1"
            file = incoming.document
        m5 = M.Manager()
        m5.bot = TelegramClient(None, 1, "h")
        m5.cfg["admin_ids"] = [111]
        m5.fsm = {}
        took = await m5.accept_admin_backup_file(Ev())
        latest = os.path.join(M.BASE_DIR, "jafj_backup_latest.zip")
        check("S5_admin_zip_saved_for_restore",
              took and os.path.isfile(latest), f"took={took} latest={os.path.isfile(latest)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        results["EXCEPTION"] = f"{type(e).__name__}: {e}"

    good = all(v is True for v in results.values()) and "EXCEPTION" not in results
    print("ALL:", "PASS" if good else "FAIL")

asyncio.run(main())
''')


def main():
    shutil.rmtree(ROOT, ignore_errors=True)
    os.makedirs(APP, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(STORE, exist_ok=True)
    for name in ("manager_82.py", "95.py"):
        shutil.copy2(os.path.join(SRC, name), APP)
    tel = os.path.join(APP, "telethon")
    os.makedirs(os.path.join(tel, "sessions"), exist_ok=True)
    # package layout used by `from telethon.sessions import StringSession`
    with open(os.path.join(tel, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_INIT)
    os.makedirs(os.path.join(tel, "sessions"), exist_ok=True)
    # sessions is a module in the other tests, not a package. Match that.
    shutil.rmtree(os.path.join(tel, "sessions"))
    with open(os.path.join(tel, "sessions.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_SESS)
    with open(os.path.join(tel, "errors.py"), "w", encoding="utf-8") as f:
        f.write("class FloodWaitError(Exception):\n    def __init__(self, seconds=0, *a, **k):\n        self.seconds = seconds\n")
    env = dict(os.environ)
    env["DATA_DIR"] = DATA
    env["FAKE_BACKUP_DIR"] = STORE
    env["PORT"] = "8366"
    env["BACKUP_CHAT"] = "111"
    for k in ("BOT_TOKEN", "API_ID", "API_HASH", "ADMIN_IDS", "BACKUP_EVERY"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", DRIVER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=120)
    out = p.stdout + p.stderr
    print(out)
    return 0 if "ALL: PASS" in out else 1


if __name__ == "__main__":
    sys.exit(main())
