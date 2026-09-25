#!/usr/bin/env python3
"""تک‌پیامِ پشتیبان — پیوی مدیر نباید بعد از هر ری‌استارت/دیپلوی Render پر از
فایلِ پشتیبان شود.

باگ: هر تغییرِ داده و هر بوتِ تازه (اثرانگشتِ اولِ بوت همیشه «عوض‌شده» بود)
یک پیامِ پشتیبانِ تازه در پیوی مدیر می‌فرستاد؛ نتیجه: انباشتِ فایل بعد از هر
رست/آپدیت روی Render — «خیلی رو مخ».

فیکس:
  * قبل از ارسال، آخرین پیامِ پشتیبانِ خود ربات در چت مقصد پیدا می‌شود و
    مدیای «همان» پیام edit می‌شود (تلگرام اجازه‌ی edit مدیای بات را دارد).
  * اگر edit ممکن نبود (سقف ۴۸ ساعت تلگرام)، پیام تازه می‌رود و قبلی درجا
    پاک می‌شود — باز هم فقط یک پیام می‌ماند.
  * اثرانگشتِ آخرین پشتیبان روی دیسک (.jafj_backup_fp) ذخیره می‌شود تا بعد از
    ری‌استارتِ بدون تغییرِ داده، اصلاً پشتیبانِ تکراری نرود؛ و اگر مدیر
    تک‌پیام را پاک کرده باشد، دوباره ساخته می‌شود.
  * پیام‌های اضافیِ مانده از نسخه‌های قبل هم با سقفِ محدود پاک می‌شوند.
  * بازیابی (restore) همان‌طور که بود کار می‌کند: تازه‌ترین پیامِ دارای
    JAFJBACKUP1 را پیدا می‌کند — با یک پیام هم درست است.
"""
import os, sys, shutil, subprocess, tempfile, textwrap

ROOT = os.path.join(tempfile.gettempdir(), "jafj_backup_single_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")
FAKESTORE = os.path.join(ROOT, "fakestore")
SRC_REPO = os.environ.get("REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAKE_INIT = textwrap.dedent('''
import os, shutil

MESSAGES = []          # newest-first: [FakeMsg, ...]
_next_id = [100]
EDIT_FAIL = [False]    # شبیه‌سازی سقف ۴۸ ساعته‌ی edit تلگرام


class FakeMsg:
    def __init__(self, mid, caption, sender_id, fpath):
        self.id = mid
        self.caption = caption or ""
        self.text = caption or ""
        self.sender_id = sender_id
        self._fpath = fpath
        self.edits = 0


class U:
    username = "fakebot"
    id = 111


class TelegramClient:
    def __init__(self, session, api_id, api_hash, **kw):
        self.session = session
        self.api_id = api_id
        self.api_hash = api_hash

    async def connect(self):
        return

    async def is_user_authorized(self):
        return True

    async def start(self, bot_token=None):
        return self

    async def disconnect(self):
        return

    async def get_me(self):
        return U()

    def on(self, *a, **k):
        def deco(fn):
            return fn
        return deco

    async def run_until_disconnected(self):
        return

    async def send_message(self, *a, **k):
        class R:
            id = 1
        return R()

    async def get_entity(self, x):
        class E:
            username = None
        return E()

    async def send_file(self, target, fpath, caption=None, **kw):
        _next_id[0] += 1
        mid = _next_id[0]
        dst = os.path.join(os.environ["FAKE_BACKUP_DIR"], f"msg_{mid}.zip")
        shutil.copy2(str(fpath), dst)
        msg = FakeMsg(mid, caption, 111, dst)
        MESSAGES.insert(0, msg)
        return msg

    async def edit_message(self, target, message=None, text=None, *, file=None, **kw):
        if EDIT_FAIL[0]:
            raise RuntimeError("MessageNotMutable: too old (simulated 48h)")
        for m in MESSAGES:
            if m.id == message:
                m.caption = text or ""
                m.text = m.caption
                m.edits += 1
                if file:
                    dst = os.path.join(os.environ["FAKE_BACKUP_DIR"], f"msg_{m.id}.zip")
                    shutil.copy2(str(file), dst)
                    m._fpath = dst
                return m
        raise RuntimeError("message not found")

    async def delete_messages(self, target, ids, **kw):
        ids = set(ids or ())
        MESSAGES[:] = [m for m in MESSAGES if m.id not in ids]

    def iter_messages(self, target, limit=50, **kw):
        async def _gen():
            for m in list(MESSAGES)[:limit]:
                yield m
        return _gen()

    async def download_media(self, msg, file=None, **kw):
        src = getattr(msg, "_fpath", None)
        if file is None:
            return src
        shutil.copy2(str(src), str(file))
        return str(file)


class Button:
    @staticmethod
    def inline(*a, **k):
        return ("inline", a, k)

    @staticmethod
    def url(*a, **k):
        return ("url", a, k)

    @staticmethod
    def request_phone(*a, **k):
        return ("phone", a, k)

    @staticmethod
    def text(*a, **k):
        return ("text", a, k)

    @staticmethod
    def clear(*a, **k):
        return None


class events:
    class NewMessage:
        def __init__(self, *a, **k):
            pass

    class CallbackQuery:
        def __init__(self, *a, **k):
            pass
''')

FAKE_SESSIONS = textwrap.dedent('''
class StringSession:
    def __init__(self, s=""):
        if s == "CORRUPTED":
            raise ValueError("corrupted")
        self._s = s or ""
        self.dc_id = 1
        self.server_address = "127.0.0.1"
        self.port = 443
        self.auth_key = b"fake"
    def save(self):
        return self._s
class SQLiteSession:
    def __init__(self, *a, **k):
        pass
    def set_dc(self, *a, **k):
        pass
    def save(self):
        pass
    def close(self):
        pass
''')

FAKE_ERRORS = textwrap.dedent('''
class FloodWaitError(Exception):
    def __init__(self, seconds=0, *a, **k):
        super().__init__(f"FloodWait {seconds}")
        self.seconds = int(seconds or 0)
class PhoneNumberBannedError(Exception): pass
class PhoneNumberInvalidError(Exception): pass
class SessionPasswordNeededError(Exception): pass
class PhoneCodeInvalidError(Exception): pass
class PhoneCodeExpiredError(Exception): pass
class UserNotParticipantError(Exception): pass
''')

DRIVER = textwrap.dedent('''
import os, sys, asyncio, zipfile
sys.path.insert(0, os.getcwd())
import manager_82 as M
from telethon import TelegramClient, MESSAGES, EDIT_FAIL
from telethon.sessions import StringSession


def backup_tagged():
    return [m for m in MESSAGES if "JAFJBACKUP1" in (m.caption or "")]


def make_mgr():
    m = M.Manager()
    m.bot = TelegramClient(StringSession("B"), 1, "hash")
    return m


def checkpoint(m):
    for conn in (m.db, m.shop):
        try:
            conn.c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.c.commit()
        except Exception:
            pass


async def main():
    results = {}
    try:
        # ── S1: اولین پشتیبان → دقیقاً یک پیام ──
        m = make_mgr()
        m.db.add(111, "testuser", "Test User", 0)
        m.db.set(111, session="SESSION_" + "Y"*60, phone="+989120000000",
                 status="active", phone_verified=1, tg_id=111)
        checkpoint(m)
        ok1, _ = await m.backup_once(force=True)
        s1 = ok1 and len(MESSAGES) == 1 and len(backup_tagged()) == 1
        results["S1_first_backup_one_message"] = bool(s1)

        # ── S2: تغییر داده → همان پیام edit می‌شود، پیام جدید نمی‌آید ──
        first_id = MESSAGES[0].id
        m.db.log(111, "test_change", "data changed")
        checkpoint(m)
        ok2, _ = await m.backup_once(force=False)
        s2 = (ok2 and len(MESSAGES) == 1 and MESSAGES[0].id == first_id
              and MESSAGES[0].edits == 1)
        results["S2_data_change_edits_same_message"] = bool(s2)

        # ── S3: بدون تغییر → هیچ کاری نمی‌کند ──
        before_edits = MESSAGES[0].edits
        ok3, msg3 = await m.backup_once(force=False)
        s3 = ((not ok3) and "بدون تغییر" in msg3
              and len(MESSAGES) == 1 and MESSAGES[0].edits == before_edits)
        results["S3_untouched_when_no_change"] = bool(s3)

        # ── S4: مدیر تک‌پیام را پاک کرده → دوباره ساخته می‌شود ──
        MESSAGES.clear()
        ok4, _ = await m.backup_once(force=False)
        s4 = ok4 and len(MESSAGES) == 1 and len(backup_tagged()) == 1
        results["S4_deleted_message_is_recreated"] = bool(s4)

        # ── S5: edit ناممکن (۴۸ ساعت تلگرام) → پیام تازه جایگزین، باز یکی ──
        old_id = MESSAGES[0].id
        EDIT_FAIL[0] = True
        m.db.log(111, "test_change2", "data changed again")
        checkpoint(m)
        ok5, _ = await m.backup_once(force=False)
        EDIT_FAIL[0] = False
        s5 = (ok5 and len(MESSAGES) == 1 and len(backup_tagged()) == 1
              and MESSAGES[0].id != old_id)
        results["S5_edit_fallback_still_one_message"] = bool(s5)

        # ── S6: اثرانگشت روی دیسک مانده → بوتِ جدید، بدون تغییر، چیزی نمی‌فرستد ──
        m2 = make_mgr()
        ok6, msg6 = await m2.backup_once(force=False)
        s6 = (not ok6) and "بدون تغییر" in msg6 and len(MESSAGES) == 1
        results["S6_reboot_no_spam_fp_persisted"] = bool(s6)

        # ── S7: انباشتِ قدیمی (نسخه‌های قبل) پاک می‌شود؛ پشتیبانِ چتِ دیگر نه ──
        keep = backup_tagged()[0]
        for _ in range(3):
            from telethon import FakeMsg as _FM
            _next = keep.id + len(MESSAGES) + 7
            MESSAGES.insert(1, _FM(_next, "JAFJBACKUP1 old pile", 111, keep._fpath))
        from telethon import FakeMsg as _FM2
        MESSAGES.insert(1, _FM2(99999, "JAFJBACKUP1 other chat owner", 999, keep._fpath))
        await m2._cleanup_extra_backup_msgs("target", keep_id=keep.id)
        left = backup_tagged()
        s7 = (len(left) == 2 and keep.id in [x.id for x in left]
              and 99999 in [x.id for x in left])
        results["S7_legacy_pile_cleaned_foreign_kept"] = bool(s7)

        # ── S8: پیامِ تک، تازه و قابل بازیابی است (tag در کپشن) ──
        s8 = ("JAFJBACKUP1" in MESSAGES[0].caption
              and "clients=" in MESSAGES[0].caption)
        results["S8_caption_keeps_restore_tag"] = bool(s8)
    except Exception as e:
        import traceback
        traceback.print_exc()
        results["EXCEPTION"] = f"{type(e).__name__}: {e}"

    for k in sorted(results):
        print(f"{k} {'PASS' if results[k] is True else 'FAIL ' + str(results[k])}")
    print("SINGLE_RESULT", "PASS" if all(v is True for v in results.values()) else "FAIL")


asyncio.run(main())
''')


def reset_all():
    shutil.rmtree(ROOT, ignore_errors=True)
    for d in (APP, DATA, FAKESTORE):
        os.makedirs(d, exist_ok=True)
    for f in ("manager_82.py", "95.py"):
        shutil.copy2(os.path.join(SRC_REPO, f), APP)
    tel = os.path.join(APP, "telethon")
    os.makedirs(tel, exist_ok=True)
    open(os.path.join(tel, "__init__.py"), "w", encoding="utf-8").write(FAKE_INIT)
    open(os.path.join(tel, "sessions.py"), "w", encoding="utf-8").write(FAKE_SESSIONS)
    open(os.path.join(tel, "errors.py"), "w", encoding="utf-8").write(FAKE_ERRORS)


def main():
    reset_all()
    env = dict(os.environ)
    env["DATA_DIR"] = DATA
    env["PORT"] = "8199"
    env["FAKE_BACKUP_DIR"] = FAKESTORE
    env["BACKUP_CHAT"] = "12345"
    env.pop("BACKUP_EVERY", None)
    for k in ("BOT_TOKEN", "API_ID", "API_HASH"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", DRIVER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=120)
    out = p.stdout + p.stderr
    print("\n".join(l for l in out.splitlines()
                    if l.startswith(("S", "SINGLE", "EXCEPTION")) or "PASS" in l or "FAIL" in l)
          or out[-3000:])
    good = "SINGLE_RESULT PASS" in out
    print("single-backup-message:", "PASS" if good else "FAIL")
    if not good:
        print(out[-4000:])
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
