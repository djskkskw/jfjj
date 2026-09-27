#!/usr/bin/env python3
"""پاداش زیرمجموعه وابسته به وضعیت سلفِ معرف.

- سلف روی اکانت معرف فعال باشد → هر دعوت معتبر ۱ امتیاز (referral_points_self)
- معرف اصلاً سلف فعال نداشته باشد → هر دعوت معتبر ۲ امتیاز (referral_points)

Manager و Shop واقعی با telethon جعلی اجرا می‌شوند.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

ROOT = os.path.join(tempfile.gettempdir(), "jafj_referral_self_rate_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")
SRC_REPO = os.environ.get("REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── minimal fake telethon, enough for `import manager_82` ──
FAKE_TELETHON = textwrap.dedent('''
    class TelegramClient:
        def __init__(self, session, api_id, api_hash, **kw):
            pass
        async def connect(self):
            return
        async def is_user_authorized(self):
            return True
        async def start(self, bot_token=None):
            return self
        async def disconnect(self):
            return
        async def get_me(self):
            class U:
                username = "fakebot"
                id = 1
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
        async def send_file(self, *a, **k):
            return None
        def iter_messages(self, *a, **k):
            async def _gen():
                return
                yield
            return _gen()
        async def download_media(self, *a, **k):
            return None

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

    class _Err(Exception):
        pass
    FloodWaitError = _Err
    PhoneNumberBannedError = _Err
    PhoneNumberInvalidError = _Err
    SessionPasswordNeededError = _Err
    PhoneCodeInvalidError = _Err
    PhoneCodeExpiredError = _Err
    UserNotParticipantError = _Err
''')

FAKE_SESSIONS = textwrap.dedent('''
    class StringSession:
        def __init__(self, s=""):
            self._s = s or ""
            self.dc_id = 1
            self.server_address = "127.0.0.1"
            self.port = 443
            self.auth_key = b"fake-auth-key-1234567890"
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

    class PhoneNumberBannedError(Exception):
        pass
    class PhoneNumberInvalidError(Exception):
        pass
    class SessionPasswordNeededError(Exception):
        pass
    class PhoneCodeInvalidError(Exception):
        pass
    class PhoneCodeExpiredError(Exception):
        pass
    class UserNotParticipantError(Exception):
        pass
''')

INNER = textwrap.dedent('''
    import os, sys
    sys.path.insert(0, os.getcwd())
    import manager_82 as M

    m = M.Manager()
    ok_all = True

    def check(name, cond):
        global ok_all
        ok_all = ok_all and bool(cond)
        print("CHECK", name, "PASS" if cond else "FAIL")

    def make_user(uid, phone, **kw):
        m.ensure_client(uid)
        m.db.set(uid, phone=phone, phone_verified=1, **kw)

    check("default referral_points = 2", m.cfg["referral_points"] == 2)
    check("default referral_points_self = 1", m.cfg["referral_points_self"] == 1)

    # معرف بدون سلف
    make_user(100, "09120000100", status="new", session="")
    # معرف با سلف فعال (سشن + active + منقضی‌نشده)
    make_user(200, "09120000200", status="active", session="SESS",
              expires_at=M.now() + 86400)
    # معرف با سلف منقضی → بدون سلف حساب می‌شود
    make_user(300, "09120000300", status="expired", session="SESS",
              expires_at=M.now() - 10)
    # معرف با سلف حالت امتیازی (active, expires_at=0)
    make_user(400, "09120000400", status="active", session="SESS", expires_at=0)

    check("no self -> not active", not m.self_active(100))
    check("active self -> active", m.self_active(200))
    check("expired self -> not active", not m.self_active(300))
    check("points-mode self -> active", m.self_active(400))

    check("rate no self = 2", m.referral_points_for(100) == 2)
    check("rate active self = 1", m.referral_points_for(200) == 1)
    check("rate expired self = 2", m.referral_points_for(300) == 2)

    def invite(ref, inv, phone):
        m.shop.set_referrer(inv, ref)
        make_user(inv, phone)
        return m.reward_verified_referral(inv)

    r = invite(100, 1001, "09120001001")
    check("no-self referrer gets 2", r == (100, 2) and m.shop.p_balance(100) == 2)
    r = invite(100, 1002, "09120001002")
    check("no-self referrer: each invite 2", m.shop.p_balance(100) == 4)
    check("reward only once", m.reward_verified_referral(1002) == (None, 0)
          and m.shop.p_balance(100) == 4)

    r = invite(200, 2001, "09120002001")
    check("active-self referrer gets 1", r == (200, 1) and m.shop.p_balance(200) == 1)
    r = invite(200, 2002, "09120002002")
    check("active-self referrer: each invite 1", m.shop.p_balance(200) == 2)

    r = invite(300, 3001, "09120003001")
    check("expired-self referrer gets 2", r == (300, 2))

    # قابل تنظیم با /set
    m.cfg["referral_points_self"] = 3
    m.cfg["referral_points"] = 5
    check("custom self rate", m.referral_points_for(200) == 3)
    check("custom no-self rate", m.referral_points_for(100) == 5)

    txt = m.referral_rate_text(200)
    check("rate text mentions active self", "فعال است" in txt)
    txt = m.referral_rate_text(100)
    check("rate text mentions no self", "فعال نیست" in txt)

    print("RESULT", "PASS" if ok_all else "FAIL")
''')


def reset():
    shutil.rmtree(ROOT, ignore_errors=True)
    os.makedirs(APP, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    for f in ("manager_82.py", "95.py"):
        shutil.copy2(os.path.join(SRC_REPO, f), APP)
    tel = os.path.join(APP, "telethon")
    os.makedirs(tel, exist_ok=True)
    with open(os.path.join(tel, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_TELETHON)
    with open(os.path.join(tel, "sessions.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_SESSIONS)
    with open(os.path.join(tel, "errors.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_ERRORS)


def run_inner(inner, port):
    env = dict(os.environ)
    env["DATA_DIR"] = DATA
    env["PORT"] = str(port)
    env["JAFJ_PORT"] = str(port)
    for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID",
              "JAFJ_HOSTED", "JAFJ_LOGIN_RETRY", "BACKUP_CHAT", "BACKUP_EVERY",
              "BOT_TOKEN", "API_ID", "API_HASH"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", inner], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=60)
    return p.stdout + p.stderr


def test_referral_rate_depends_on_self():
    reset()
    out = run_inner(INNER, 8171)
    checks = [l for l in out.splitlines() if l.startswith("CHECK")]
    print("\n".join(checks) or out[-3000:])
    good = "RESULT PASS" in out
    if not good:
        print(out[-3000:])
    return good


if __name__ == "__main__":
    ok = test_referral_rate_depends_on_self()
    print("ALL:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
