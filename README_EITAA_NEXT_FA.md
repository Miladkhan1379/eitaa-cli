# Eitaa Next v0.9 — بسته ارتقای تجمعی برای eitaa-cli

این بسته روی Fork فعلی `eitaa-cli` اعمال می‌شود و قابلیت‌های v0.6 تا v0.8.1 را نگه می‌دارد. قبل از Patch، از فایل‌های تغییرپذیر Backup خودکار در `.eitaa-next-backup/` ساخته می‌شود.

## امکانات اصلی v0.9

### 1) انتخاب تعاملی کانال/گروه
دیگر لازم نیست Peer را دستی پیدا یا کپی کنید:

```powershell
eitaa sources pick medical --kind channel
```

جدول کانال‌ها نمایش داده می‌شود، شماره را انتخاب می‌کنید و بعد در تمام فرمان‌ها می‌نویسید:

```powershell
eitaa sync watch source:medical --once
```

### 2) دانلود گروهی حرفه‌ای و Resume در سطح Job

```powershell
eitaa downloads run source:medical --type video --type document --after 2026-01-01 --limit 5000 -o .\downloads
```

ویژگی‌ها:
- ادامه Job بعد از قطع برنامه
- عدم دانلود دوباره فایل‌های موفق
- Retry فایل‌های ناموفق
- فیلتر photo/video/document/audio/voice/gif
- فیلتر بازه تاریخ
- محدودیت اندازه Document/Video در صورت موجود بودن metadata
- Progress bar
- SQLite ledger

وضعیت:

```powershell
eitaa downloads status
eitaa downloads failures JOB_ID
eitaa downloads retry JOB_ID
```

> Resume در v0.9 در سطح message/job است. فایل موفق دوباره دانلود نمی‌شود. Resume بایت‌به‌بایت وسط یک فایل تا زمانی که Range/offset دانلود ایتا روی سرور واقعی اعتبارسنجی نشود ادعا نمی‌شود.

### 3) Hybrid Update Engine

```powershell
eitaa sync capabilities
```

سپس:

```powershell
eitaa sync hybrid source:medical --poll 5
```

این حالت `updates.getState/getDifference` را امتحان می‌کند و در هر خطا، gap بزرگ یا پاسخ پشتیبانی‌نشده به Sync incremental مطمئن برمی‌گردد. Polling همچنان safety net است تا تغییرات ناشناخته API باعث از دست رفتن پیام نشوند.

### 4) Multi-account

اکانت‌های لاگین‌شده:

```powershell
eitaa accounts list
eitaa accounts check
```

تغییر اکانت فعال:

```powershell
eitaa accounts use work
```

Watch همزمان چند اکانت:

```powershell
eitaa fleet watch source:medical --profile work --profile personal --poll 5
```

اگر `--profile` ندهید، همه Profileهای authenticated استفاده می‌شوند. State هر اکانت در SQLite جدا ذخیره می‌شود.

### 5) سرویس دائمی Windows و Linux/VPS

Linux user systemd (بدون root برای خود unit):

```bash
eitaa service systemd source:medical --install
```

لاگ:

```bash
journalctl --user -u eitaa-next-sync.service -f
```

Windows Task Scheduler + restart loop:

```powershell
eitaa service windows source:medical --install
```

### 6) Web Dashboard

```powershell
eitaa web start
```

سپس:

```text
http://127.0.0.1:8765
```

پنل شامل:
- Accounts
- Sources
- Sync checkpoints
- Failed automation actions
- Download jobs
- Send message
- Schedule message
- Sync once
- `/healthz`
- `/metrics` با خروجی Prometheus text format

برای bind روی شبکه، Token لازم است:

```powershell
eitaa web start --host 0.0.0.0 --token "CHANGE-ME"
```

### 7) Automation Wizard

```powershell
eitaa automation wizard --config automations.json
```

برای ساخت ruleهای رایج بدون ویرایش دستی JSON.

### 8) n8n Starter Workflow

داخل پوشه `n8n/` فایل importable قرار دارد:

```text
n8n/eitaa-next-webhook-workflow.json
```

## نصب

PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install-eitaa-next.ps1 "D:\milad\Project\eitaa-cli\eitaa-cli"
```

یا مستقیم با Python:

```powershell
python .\apply_eitaa_next.py "D:\milad\Project\eitaa-cli\eitaa-cli"
```

## تست بعد از نصب

```powershell
cd D:\milad\Project\eitaa-cli\eitaa-cli
.venv\Scripts\Activate.ps1
python -m compileall -q src\eitaa_cli
pytest -q
```

Smoke test:

```powershell
eitaa next doctor --probe-updates
eitaa accounts list
eitaa sync capabilities
eitaa sources pick test --kind channel
eitaa downloads status
eitaa web start
```

## Peer پیشنهادی

برای PowerShell username را بدون `@` هم می‌توانید بدهید:

```powershell
eitaa peers resolve rayat_info
```

برای کار طولانی بهتر است یک Alias بسازید:

```powershell
eitaa sources add medical rayat_info --label "Rayat"
eitaa sync hybrid source:medical
```

## نکته امنیتی

Eitaa Next غیررسمی است و به Eitaa وابستگی رسمی ندارد. Session token را مثل رمز عبور نگهداری کنید. Web dashboard به‌صورت پیش‌فرض فقط روی localhost اجرا می‌شود؛ آن را بدون Token مستقیماً روی اینترنت expose نکنید.
