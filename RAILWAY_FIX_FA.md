# فیکس دیپلوی Railway — چه مشکلی بود و چه شد

## مشکل اصلی که باعث Fail شدن دیپلوی می‌شد

۱. **هلث‌چک Railway هیچ پورتی نمی‌دید:**
   - Railway متغیر `$PORT` را تزریق می‌کند و انتظار دارد `0.0.0.0:$PORT` در چند ثانیه اول بالا بیاید.
   - `manager_82.py` هلث‌سرور را داخل یک Thread بعد از importها بالا می‌آورد، ولی اگر قبل از آن GitHub pull طول بکشد یا مدیر کرش کند و اسکریپت ۵ ثانیه بخوابد (`NAP_BASE`)، در آن بازه هیچ پورتی Listen نمی‌کند.
   - نتیجه: Railway می‌نویسد `1/1 replicas never became healthy! Healthcheck failed!` و دیپلوی را Fail می‌کند.

۲. **Dockerfile قدیمی:**
   - `pip install -r requirements.txt` بدون `--no-cache-dir` و بدون `ca-certificates` بود.
   - `ENV PORT` و `EXPOSE` نداشت.
   - لاگ‌ها بافر می‌شدند (`PYTHONUNBUFFERED` نبود).

۳. **railway.json قدیمی و Deprecated:**
   - Railway از اواخر ۲۰۲۵ `railway.json` را Deprecated کرده و می‌گوید `Config as Code is deprecated, use Infrastructure as Code`.
   - فایل قبلی `healthcheckPath` و `healthcheckTimeout` نداشت و اسکیمای `$schema` هم نداشت.

۴. **تست SIGTERM شکننده:**
   - تست `test_railway_selfbot_bootstrap` داخل signal handler از `print` استفاده می‌کرد که در پایتون ناامن است و با اضافه شدن هلث‌سرور جدید، Race Condition باعث `RuntimeError: reentrant call inside BufferedWriter` می‌شد.

## چه فیکس شد

### 1) `railway-start.sh` — هلث‌سرور فوری در entrypoint
- همین اول کار، قبل از هر منطق دیگری، یک HTTP سرور مینیمال روی `0.0.0.0:$PORT` بالا می‌آید:
  - هر مسیر (`/`, `/healthz`, `/health`) را با `200 JAFJ OK` جواب می‌دهد.
  - تا آخر عمر کانتینر زنده می‌ماند، حتی وقتی مدیر کرش می‌کند و در حال `sleep 5s` است.
  - لاگ‌هایش به `stderr` می‌رود تا با `stdout` خود مدیر تداخل نکند.
- `stop_health()` اضافه شد تا هنگام `SIGTERM` تمیز بسته شود.
- `log()` به `stderr` رفت تا لاگ‌های Railway مرتب‌تر باشد.
- پیام `health still on :$PORT` در لاگ ری‌استارت اضافه شد تا بفهمی هلث‌سرور هنوز زنده است.

### 2) `Dockerfile`
```dockerfile
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PORT=8080
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt
EXPOSE 8080
```
- حالا حتی اگر Railway به‌جای Nixpacks از Dockerfile استفاده کند، بیلد تمیز می‌ماند.
- `ca-certificates` برای TLS تلگرام لازم است.

### 3) `railway.json`
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": { "builder": "dockerfile", "dockerfilePath": "Dockerfile" },
  "deploy": {
    "startCommand": "sh /opt/jafj/railway-start.sh",
    "healthcheckPath": "/healthz",
    "healthcheckTimeout": 100,
    "restartPolicyType": "onFailure",
    "restartPolicyMaxRetries": 10
  }
}
```
- `healthcheckPath: /healthz` اضافه شد (entrypoint و خود مدیر هر دو آن را جواب می‌دهند).
- `healthcheckTimeout: 100` تا Railway فرصت کافی بدهد.
- `$schema` برای اینکه Railway CLI اخطار ندهد.

### 4) `render-start.sh`
- `PORT` پیش‌فرض `10000` ست شد تا با Render هماهنگ باشد.

### 5) تست‌ها
- `test_railway_selfbot_bootstrap.py` : signal handler از `print` ناامن به `os.write` امن تغییر کرد.
- `test_gh_data_sync.py` : چک سخت‌گیرانه `stop_sync\n        exit` به چک انعطاف‌پذیر تغییر کرد و چک `stop_health` اضافه شد.

## چطور روی Railway دیپلوی کنی (مرحله‌به‌مرحله)

1. **ریپو را به Railway وصل کن:**
   - New Project → Deploy from GitHub → همین ریپو
   - Railway خودش `Dockerfile` را تشخیص می‌دهد (چون `railway.json` می‌گوید builder=dockerfile).

2. **متغیرهای محیطی را بگذار:**
   - `BOT_TOKEN` : توکن رباتت از @BotFather (الزامی)
   - `BACKUP_CHAT` : آیدی عددی پیوی خودت یا کانال خصوصی بکاپ (اختیاری ولی پیشنهادی)
   - `DATA_DIR` : `/data` (اگر Volume داری)
   - `PORT` : خود Railway می‌گذارد، دستی نزن
   - اگر می‌خواهی بکاپ گیت‌هاب داشته باشی:
     - `DATA_GITHUB_TOKEN` : توکن کلاسیک گیت‌هاب با دسترسی `repo`
     - `DATA_GITHUB_REPO` : مثلاً `djskkskw/jfjj-data` (ریپوی خصوصی جدا)

3. **Volume:**
   - Add Volume → Mount Path = `/data` → Size 1GB
   - **هرگز** Volume را روی `/app` یا `/opt/jafj` مانت نکن! چون کد ایمیج پنهان می‌شود و هر دیپلوی بی‌اثر می‌ماند. همیشه `/data`.

4. **Start Command:**
   - در داشبورد Railway چک کن Start Command همان `sh /opt/jafj/railway-start.sh` باشد (از `railway.json` می‌آید).

5. **Health Check:**
   - اگر داشبورد اجازه می‌دهد، Health Check Path را `/healthz` بگذار.

6. **Redeploy:**
   - بعد از هر تغییر کد، حتماً Redeploy بزن تا ایمیج دوباره ساخته شود.

## اگر هنوز Fail می‌شود، لاگ‌ها را چک کن

- `SELFBOOT: health on 0.0.0.0:XXXX` باید همان اول بیاید.
- `SELFBOOT: code=/opt/jafj data=/data` باید data را `/data` نشان دهد، نه `/app` اگر Volume روی `/app` است.
- اگر `WARNING: /app holds a copy of manager_82.py` دیدی، یعنی Volume را اشتباه روی `/app` مانت کرده‌ای.
- اگر `manager crashed X times — giving up` دیدی، یعنی توکن یا API_ID مشکل دارد؛ `BOT_TOKEN` را چک کن.

## نکته توکن هاردکد

داخل `manager_82.py` یک توکن هاردکد هست:
`8832561144:AAFSRpyaD4M9GWWsiltBMXs6acbbo6W0J-M`
اگر این توکن Revoke شده باشد، مدیر روی Railway به‌صورت `login_retry_forever` تا ابد تلاش می‌کند (هلث‌چک همچنان OK می‌ماند ولی ربات جواب نمی‌دهد). حتماً `BOT_TOKEN` خودت را در متغیر محیطی Railway بگذار تا جایگزین هاردکد شود.

---
فیکس‌ها تست شدند:
- `test_railway_container_layout.py` PASS
- `test_railway_selfbot_bootstrap.py` PASS
- `test_render_host.py` PASS
- `test_gh_data_sync.py` PASS
- `test_crashloop_hardening.py` PASS
