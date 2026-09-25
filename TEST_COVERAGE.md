# نقشهٔ کامل تست‌ها — چه چیزی واقعاً تست شده، چه چیزی فقط ادعا شده

> جمع‌بندی: **۳۱ فایل تست / ۱۱٬۱۶۱ خط / ۱۵۷۰+ سنجه**. همه در وضعیت فعلی **سبز**.
> اجرا: `python3 tests/test_<name>.py` (هر فایل مستقل و self-contained است؛ نیازی به pytest نیست).

---

## ۱. دو سبکِ راستی‌آزمایی در این مجموعه

| سبک | معنی | اعتبار |
|---|---|---|
| **رفتاری (Behavioral)** | کد واقعی پروژه *اجرا* می‌شود — import مستقیم ماژول، استخراج تابع و فراخوانی‌اش، یا اجرای اسکریپت/زیرفرایند در sandbox با ابزارهای shim — و **اثر** آن سنجیده می‌شود | ✅ «واقعاً تست شده» |
| **تأیید متن کد (Source-string)** | `"<عبارت>" in src` — فقط وجود یک رشته در سورس چک می‌شود | ⚠️ «فقط ادعا»؛ اگر آن خط *هیچ‌وقت اجرا نشود*، تست باز هم سبز می‌ماند |

**آمار دقیق:** ۱۶ فایل کاملاً رفتاری (۰ تأیید متنی) + ۱۴ فایل ترکیبی (رفتاری + مجموعاً **۹۴** تأیید متنی).

---

## ۲. جدول کامل تست‌ها

### الف) کاملاً رفتاری — صفر تأیید متنی (۱۶ فایل)

| تست | چه چیزی را **واقعاً** اجرا و راستی‌آزمایی می‌کند |
|---|---|
| `test_backup_restore.py` | توابع `backup_once`/`restore_from_backup` از `manager_82.py` استخراج و با ذخیرهٔ تلگرامِ فایل‌محور اجرا می‌شوند: بکاپ در Saved Messages خودِ ربات (PM_BOT_ID=self)، پیامِ نشانهٔ MD5، فایل zip با metadata، پین پیام تکی، بنرِ شکست آپلود، بازیابی در DATA_DIR خالی (creds / فایل session / کپی‌های محلی / manager.db)، **استفادهٔ مجدد از session بازیابی‌شده در بوت بعدی** (پورت‌های ۸۱۵۱/۸۱۵۲)، ردِّ فینگرپرینت ناهمسان (کانال public پذیرفته نمی‌شود) |
| `test_backup_single_message.py` | بکاپ دوم پیام قبلی را حذف می‌کند → Saved Messages دقیقاً ۱ پیام؛ صحت metadata داخل zip (باید `backup_format` نسخهٔ ۲ و `client: telethon` داشته باشد)؛ کشتنِ وسط ترتیب → بکاپ بعدی پیام نیمه‌کاره را هم پاک می‌کند |
| `test_config_env.py` | بارگذاری تنظیمات با envهای مختلف در زیرفرایند واقعی: `DATA_DIR=.data1` → پوشه ساخته می‌شود؛ بدون `DATA_DIR` → پیش‌فرض ساخته می‌شود؛ `PERSIAN_LANG=0/1` واقعاً `T()` را برمی‌گرداند؛ `PORT` پیش‌فرض ۸۰۸۰؛ `BASE_URL` در بنر؛ `ADMIN_SECRET` در `/env`؛ دیتابیس نباید داخل workdir باشد |
| `test_crashloop_hardening.py` | حالت run با خطای `RuntimeError` → `start_watcher` زنده می‌ماند؛ مسیر `KeyboardInterrupt` (۳ سناریو) |
| `test_duplicate_instances.py` | `parse_beacon` با پیام‌های beacon خودی/غیرخودی/کهنه/معمولی؛ پایداری deploy-id (هگز ≥۶)؛ تشخیص توکن مرده (`is_dead_token_error`) با دسته‌بندی خطاها؛ ترتیب توکن‌های کاندید (config vs health-check) |
| `test_exchange_group_gate.py` | گروه خصوصی → مجاز؛ گروه public → رد با متن «خصوصی»؛ خطای دسترسی → بی‌صدا |
| `test_login_bot.py` | ۳ سناریوی زیرفرایندی: لاگین کامل (شماره/کد/رمز) → فایل session + StringSession نوشته می‌شود؛ `jafj.session` خراب → قرنطینه به `.bad` + هشدار + کارت نصب؛ کارت FSM نصب با دکمه‌های پشتیبانی |
| `test_railway_container_layout.py` | اجرای **واقعی** `render-start.sh` در sandbox با shimهای `python3/pip3/rm`: نشانه‌های بوت، بازیابی *قبلِ* بوت، بازنویسی config به `/data/config/manager_config.json`، envها (`DATA_DIR=/data/data`، بدون `BACKUP_PRIVATE_CHAT_ID`)، حالت repair (ادغام config + کلیدهای `jafj_ai.json` + بدون ری‌استارتِ لاگین)، حالت links (پیوندهای dir_link/install/scripts_link/95.py، config تکی در `/data/config`، فقط پیوندِ غایب، توکن‌ها از config) |
| `test_railway_selfbot_bootstrap.py` | حجم خالی + shim: `_clean_empty_sessions` فایل `jafj.session` صفر-بایتی را حتی با وجود creds پاک می‌کند (هر دو چیدمان)؛ `creds_aware_repair_mode` وقتی creds هست دست به فایل‌های سلف‌بات نمی‌زند؛ جریان لاگین روی حجم برهنه |
| `test_render_host.py` | اجرای **واقعی** `entrypoint.sh` + `render-start.sh` با shimهای `python3/pip3/kill/curl/rm` و `mkdir` ضبط‌شونده: پیام بوت، بازیابی فقط روی حجم غیرخالی، ساخت خودکار base dir با هشدار، نشانهٔ پایانی، پاک‌سازی قفل `/app` و `/tmp/manager82.pid`، **`/healthz` با `http.server` واقعی stdlib** (کلاس `HealthHandler` اجرا و با curl shim زده می‌شود)، نوشتنِ صفر بایت در workdir (حتی بعد از shim شدن `mkdir`)، حالت repair دست به سلف‌بات نمی‌زند، `restart_synced_selfbot_session` پوشهٔ سلف‌بات را پاک نمی‌کند (رگرسیون wipe) |
| `test_restore_resilience.py` | بازیابیِ اطلاعات بعد از دیپلوی با telethon جعلیِ **چندچتی**: پاک‌شدنِ کامل `DATA_DIR` (شبیه‌ی دیپلوی) → بوتِ تازه → `startup_restore`؛ `_reload_cfg_from_disk` (اولین `cfg.save()` بعد از بازیابی تنظیماتِ بازیابی‌شده را نمی‌پَراند — هم مسیر بوت، هم مسیرِ دستی `.restore`)؛ `prefer_media` (پیامِ متنیِ نقل‌قولیِ بی‌فایل انتخاب نمی‌شود)؛ `_find_backup_anywhere` (پیدا کردنِ تک‌پیامِ پشتیبان در چتِ دیگر وقتی چتِ مقصد خالی است)؛ ادامه‌دادنِ `backup_once` از پیامِ پشتیبانِ قبلی وقتی مقصد برای ربات **در دسترس نیست** (`_backup_target_reachable` → edit همان پیام، صفر پیام در چتِ اشتباه) و رگرسیونِ جهتِ مخالف: مقصدِ سالمِ خالی (انتقالِ عمدیِ `BACKUP_CHAT`) پیامِ تازهٔ خودش را می‌گیرد؛ تلاشِ دوباره‌ی موقعِ بوت و پیامِ وضعیتِ بازیابی (موفق/ناموفق) در پیوی مدیر؛ بی‌اثر بودنِ بازیابی وقتی دیتابیس پر است. **۱۷ سنجه؛ هر ۷ جهشِ معکوس (حذفِ هر فیکس) توسط همین تست گرفته می‌شود** |
| `test_saved_panel.py` | دستور `.info` سلف‌بات → پنل واقعی در Saved Messages با ۶ دکمه باز می‌شود؛ ثبت هر دو جهتِ رویداد ورودی؛ حفظ هندلر `EX_INCOMING`؛ ضدتکرار (ارسال مجدد پنل را دوباره باز نمی‌کند) |
| `test_say_dedup.py` | ضدتکرار `say` با JSON تنظیمات (فراخوانی تکراری در هر دو مسیرِ run نادیده گرفته می‌شود)؛ قفل `say_active` اجرای هم‌زمان را می‌اندازد؛ قفل `say_unconfirmed` تکرار در ۴ ثانیه را نادیده می‌گیرد؛ متن یکسان به هدف یکسان دوبار نمی‌رود؛ پیام بزرگ به تاپیک گروه بی‌صدا می‌رود |
| `test_selfbot_paths.py` | خروجی‌های سلف‌بات (session و `jafj_creds.json`) واقعاً در `DATA_DIR/clients/<uid>/` نوشته می‌شوند نه workdir؛ محتوای JSON و کلیدها درست؛ مجوز فایل‌ها `600` |
| `test_shutdown_cancel.py` | ۴ سناریو: `_shutdown` وسط عملیات ادعا → هشدار + await + نشانهٔ done (کنسل نرم)؛ خروج اجباریِ setup لاگین گیرکرده را می‌کشد؛ بعد از shutdown کروتن‌های لاگین نادیده گرفته می‌شوند (رگرسیون `capture_for_agent`)؛ backoff نمایی واقعی `1→2→4→8s` |
| `test_timers.py` | `calc_checkin` با جیتر ۶ساعت+۶۰دقیقه (سقف طول شناسه)؛ `relink_checkin` ۲ ساعت؛ `renew_reminder` روزهای [۳,۱] با واژه‌های فارسی؛ ترکیب ساعت/دقیقهٔ `startup_delay`؛ قالب `seconds_minutes_format` |

### ب) ترکیبی — رفتاری + تأیید متنِ کد (۱۴ فایل، ۹۴ تأیید متنی)

| تست | رفتاری (واقعاً اجرا می‌شود) | فقط-متنی (`in src`) |
|---|---|---|
| `test_op_serialization.py` | **پرحجم‌ترین تست رفتاری:** `95.py` واقعاً import و `ExCooldown` با asyncio واقعی رانده می‌شود: کول‌داون هر action، معنای key/one-per-x، purge، `since_done`، بازهٔ gap تطبیقی `[15–20]` با زمان fake، **رگرسیون فاصلهٔ هم‌زمانی (≥۰٫۰۵s با دو task هم‌زمان)**، **رگرسیون deadline فلوت (≥۳۰s)**، زمان‌بندی `scheduled_check_in`/`check_allowed_now` | ۲۰: نام‌های فراخوانی `ex_cd.action(...)` در حلقه‌های run + متن ثابت‌های gap |
| `test_tutorial_sections.py` | افزودن/ویرایش بخش با لیبل/ایموجی/یادداشت/متن/تاخیر/دکمه؛ toggle+جابه‌جایی+حذف؛ done؛ fallback متن قدیمی؛ ارسال هر بخش با `_send` (تاخیر در حالت تست پنل نادیده گرفته می‌شود)؛ اعتبارسنجی فرمت لینک دکمه؛ ارقام فارسی («۵» → ۵s)؛ «۱۰ دقیقه» → ۶۰۰s | ۱۲: توکن‌های FSM و callback، پارس ثانیه/دقیقه/ساعت، نمایش تاخیر، مهاجرت متن قدیمی به بخش‌ها |
| `test_claim_flow_fixes.py` | موتور ادعا با telethon جعلی: strikes/یادآوری‌ها per-uid (جدا بودن state کاربرها)، متن kick «بدل شد»، `remind_one_limit`، سیم‌کشی `claim_env_selfbot_ok` | ۱۰: جریان بدون ورودی، یک‌بار کارت ادعا، ممنوعیت شماره/اسکرین‌شات در متن claim |
| `test_round2_update.py` | ~۴۰ سنجه: ذخیره/decay/سقف `flood_extra` (۴۰)؛ روشن/خاموش/ریست تطبیقی از پنل؛ تنظیمات flood/decay/uptime/permanent با ارقام فارسی و فرمت خراب (مقدار دست‌نخورده می‌ماند)؛ `permanent=0` = ∞؛ نمایش/تنظیم جیتر و پنجرهٔ ۰؛ **مهاجرت مقادیر قدیمی** (interval 20→30، strikes 3→2، recheck 24h، scan_last_time)؛ صفحهٔ وضعیت (پایه vs مؤثر) | ۹ |
| `test_tutorial.py` | ارسال آموزش/گروه‌بندی بخش‌ها/نسخهٔ تک‌پیامی (۲ گروه × بخش‌ها، حالت کپی، پیگیری id) | ۷: دکمه/FSM آموزش (`m:tut`، `tut_set`، whitelist، `tut_chat/tut_ids`) |
| `test_flood_circuit_breaker.py` | مدارشکن فلوت: توقف ۲ساعته per-chat در فلوت دوم، عبور پس از deadline، تمدید deadline | ۷: پیش‌فرض `PERSIAN_LANG`، `HANDLED_ERRORS` |
| `test_unknown_fallback.py` | `unk_fallback` با ۲۰+ ورودی (نیک گیلد، لینک، استیکر، ایموجی، دستور `/`، گفت‌وگوی محاوره‌ای)؛ پارس JSON؛ پاسخ‌های fallback؛ قطعیت با seed=1345؛ کلید cooldown صفر | ۶: پیش‌فرض‌های config و برچسب مرزها |
| `test_menu_tutorials.py` | دکمه‌های منوی کاربر + متن `/start` | ۵: توکن‌های جریان (`m:orders/wallet/ref/status/support`، راهنمای زمان دعوت) |
| `test_exchange_notjoined_flow.py` | پیری صف (<۳۰دقیقه → تعویق)؛ نشان دائمی در پنل | ۵: جای‌نگه‌دارهای متن پنل، رد لینک join داخل `check_perm` |
| `test_check_gate_flood.py` | throttle واقعی `check_gate_per_day`: سقف ۳ بررسی/روز + فاصلهٔ ۵ثانیه + قفلِ بازشونده در finally | ۵: محل فراخوانی در حلقهٔ run |
| `test_tutorial_presets.py` | جایگزینی preset (wallet/points/sub/after_run) بدون دست زدن به بقیهٔ متن؛ حفظ `T()` داخل f-string (`{T("pack_wallet")}`) | ۴: عبارت دقیق ۴ کلید، `DEFAULT_TUTORIAL`، `TUT_MENU_KEYS`، هندلر `m:tut_presets` |
| `test_spacing_algorithm.py` | `compute_action_gap` با RNG بذردار: بازهٔ پایه [۳۰–۶۰]، افزایش ساعت/فلوت ×۱۰، سقف فلوت ۱۲۰، decay پنجرهٔ hard-until (۲۰s/ساعت)، عدم سقوط زیر پایه؛ `display_gap` «۶٫۵ ثانیه» | ۲: کلیدهای config در `adaptive_config` |
| `test_exchange_reply_timing.py` | `wait_for_allow` با جیتر GAP در [۳–۱۵]s؛ جیتر پیش‌فرض بررسی دسترسی [۸–۲۵]s | ۱: مهاجرت interval 20→30 + نام‌های رزروشدهٔ ExCooldown |
| `test_claim_text.py` | `ex_render` واقعی روی موتور: متن ادعای ناموفق (بدون لینکِ طرف)، fallback «سفارشیِ ناموفق»، جریان ذخیره/نمایش/حذف متن سفارشی از config | ۱ |

---

## ۳. پوشش بر اساس زیرسیستم

| زیرسیستم | تست‌های پوشش‌دهنده | عمق پوشش |
|---|---|---|
| نصب/لاگین (StringSession/QR/کد) | `login_bot`، `selfbot_paths`، `railway_selfbot_bootstrap` | عمیق (با fake telethon) |
| احراز مالکیت فروشگاه | `claim_flow_fixes`، `claim_text` | عمیق |
| پشتیبان‌گیری/بازیابی GitHub→تلگرام | `backup_restore`، `backup_single_message` | عمیق (حمل‌ونقل جعلی) |
| موتور تعویض اکانت + سریال‌سازی عملیات | `op_serialization`، `exchange_group_gate`، `exchange_notjoined_flow`، `exchange_reply_timing`، `say_dedup`، `saved_panel` | عمیق |
| فلوت تطبیقی/مدارشکن/گپ | `spacing_algorithm`، `check_gate_flood`، `flood_circuit_breaker`، `round2_update` | عمیق |
| پاسخ خودکار متن آزاد | `unknown_fallback` | عمیق |
| پنل و سیستم آموزش | `menu_tutorials`، `tutorial`، `tutorial_presets`، `tutorial_sections` | عمیق |
| تنظیمات/env/تایمرها | `config_env`، `round2_update`، `timers` | عمیق |
| بوت استقرار (Render/Railway) | `render_host`، `railway_container_layout`، `railway_selfbot_bootstrap`، `crashloop_hardening`، `duplicate_instances`، `shutdown_cancel` | عمیق (با ابزارهای shim) |

---

## ۴. ⚠️ فقط ادعا شده / بدون پوشش — شکاف‌های واقعی

1. **حمل‌ونقل واقعی تلگرام:** همه‌ی تست‌ها کلاینت جعلی دارند. آپلود واقعی فایل به Saved Messages، دانلود واقعی نسخهٔ پشتیبان از لینک MD5، و خطاهای *واقعی* سرور تلگرام (`FloodWaitError` واقعی، خطای واقعی توکن مرده) هرگز اجرا نشده‌اند.
2. **نشست واقعی Telethon:** `jafj.session` که Telethon واقعی می‌سازد و بازسازی از StringSession با `StringSession.save()` واقعی تست نشده؛ فقط نسخه‌های fake.
3. **پلتفرم واقعی ابری:** تست‌های استقرار، اسکریپت‌ها را با `python3/pip3/curl` جعلی اجرا می‌کنند — تزریق env واقعی Render/Railway، ساخت Docker image و رفتار واقعی volume ابری پوشش داده نشده. **`Dockerfile` هیچ تست مستقیمی ندارد.**
4. **زمان واقعی حلقه‌های بلند:** `backup_loop` (۶ ساعته)، heartbeat (۶۰ ثانیه)، ارسال‌های دوره‌ای — یا با زمان fake‌اند یا فقط متنِ marker حلقه‌ها تأیید شده (`assert a > 0 and b > a` روی سورس!). اجرای واقعی چندساعته وجود ندارد.
5. **۹۴ تأیید متنی (ستون سوم جدول بالا):** فقط وجود عبارت در سورس را ثابت می‌کنند، نه اجرای آن مسیر را. خط پوشش‌داده‌نشده در آن مسیرها تست را قرمز نمی‌کند.
6. **هم‌زمانی چندپروسه‌ای روی sqlite بین چند manager واقعی:** تست‌نشده. `test_duplicate_instances` توابع beacon/توکن را مستقیم می‌سنجد، نه دو پروسه واقعی در حال رقابت.
7. **توکن‌های هاردکدشده** (`BOT_TOKEN` / `HC_CHANNEL_TOKEN`) و صحتشان مقابل تلگرام — هرگز.
8. **فشار واقعی:** صدها کاربر هم‌زمان، شبکهٔ کند/قطع‌شوندهٔ واقعی — نه.

---

## ۵. نکات اجرایی

- **تک‌تک اجرا کن:** `python3 tests/test_backup_restore.py` و… ؛ هر فایل sandbox موقت خودش را می‌سازد و به هیچ سرویسی وصل نمی‌شود.
- **دو تست فِلِک زیر بار موازی سنگین** (اجراهای همزمان ده‌ها پروسهٔ پایتون): `test_op_serialization` (assertهای زمان‌سنجی دارد) و `test_railway_selfbot_bootstrap` — standalone همیشه سبزند؛ فِلِک زمانی‌اند نه باگ.
- **تست‌های کندِ عمدی:** `shutdown_cancel` ~۱۹s، `op_serialization` ~۲۱s، `claim_flow_fixes`/`unknown_fallback` ~۶s — timeout کوتاه نگذار.
- هیچ تستی به شبکه نمی‌زند؛ برای CI امن‌اند.
