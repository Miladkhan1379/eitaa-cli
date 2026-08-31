# eitaa-next v0.8 — بسته ارتقای eitaa-cli

v0.8 یک بسته تجمعی است: اصلاحات pagination و قابلیت‌های v0.6/v0.7 را نگه می‌دارد و روی خوانایی CLI، Peerهای پایدار، source alias، عملیات روزمره و GitHub workflow تمرکز می‌کند.

## مهم‌ترین تغییر v0.8: دیگر Peer طولانی را حفظ نکن

برای کانال public:

```powershell
eitaa sources add news @my_channel --label "اخبار"
```

برای کانال/گروه بدون username هم هر Peer معتبری که از لیست گرفته‌ای بده:

```powershell
eitaa sources add private-news "channel:12345:987654321"
```

بعد از این در Sync می‌توانی فقط بنویسی:

```powershell
eitaa sync watch source:news
```

یا:

```powershell
eitaa sync watch source:news source:private-news --poll 5
```

برای دیدن aliasها:

```powershell
eitaa sources list
```

## اگر نمی‌دانی چه Peerای بدهی

```powershell
eitaa peers formats
```

و برای تبدیل یک username/name/reference به فرم مطمئن:

```powershell
eitaa peers resolve @my_channel
```

خروجی `Stable` برای سرویس طولانی‌مدت مناسب‌ترین گزینه است.

## نصب

در PowerShell داخل پوشه بسته:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install-eitaa-next.ps1 "D:\milad\Project\eitaa-cli\eitaa-cli"
```

یا:

```powershell
python .\apply_eitaa_next.py "D:\milad\Project\eitaa-cli\eitaa-cli"
```

بعد:

```powershell
cd D:\milad\Project\eitaa-cli\eitaa-cli
.venv\Scripts\Activate.ps1
python -m compileall -q src\eitaa_cli
pytest -q
```

## دستورات UI جدید

```powershell
eitaa next status
eitaa next doctor
eitaa next failures
```

و:

```powershell
eitaa sources list
eitaa peers resolve @channel
eitaa automation list automations.json
eitaa automation status automations.json
eitaa automation failures automations.json
eitaa messages export @news_channel .\exports\news.jsonl --limit 5000
```

## Sync برای n8n

بار اول فقط checkpoint:

```powershell
eitaa sync watch source:news --once
```

بعد اجرای دائمی:

```powershell
eitaa sync watch source:news `
  --poll 5 `
  --webhook "http://127.0.0.1:5678/webhook/eitaa" `
  --secret "MY_SECRET"
```

خروجی interactive حالا خلاصه است:

```text
NEW  19:05:12 #1842  channel:...  متن پیام...
EDIT 19:07:40 #1842  channel:...  متن ویرایش‌شده...
```

برای مصرف ماشینی همچنان از JSON استفاده کن:

```powershell
eitaa sync watch source:news --json
```

## Source registry

```powershell
eitaa sources add news @news_channel
eitaa sources show news
eitaa sources test news
eitaa sources remove news
```

فرمت alias در `sync` و Automation config:

```text
source:news
```

Alias در SQLite ذخیره می‌شود و پشت آن stable typed peer قرار می‌گیرد.

## قابلیت‌های مهم نسخه‌های قبل

- pagination کامل Dialog/Channel/Group
- Peer resolution امن‌تر برای اسم‌های مبهم
- ارسال و Reply/Edit/Delete/Forward
- پیام، media و forward زمان‌بندی‌شده server-side
- Scheduled message management
- Pin/Unpin/Read/Draft
- History چندصفحه‌ای
- دانلود گروهی media و profile photo
- Archive/Unarchive/Folder
- SQLite incremental sync
- `new_message` و `edited_message`
- automation actionهای forward/copy/reply/send/schedule/download/webhook
- delivery ledger برای جلوگیری از action تکراری بعد از crash
- HMAC و idempotency header برای n8n
- `updates.getState/getDifference` probe آزمایشی

## GitHub

بعد از نصب فایل‌های زیر داخل fork کپی می‌شوند:

- `.github/workflows/ci.yml`
- `.github/ISSUE_TEMPLATE/*`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `GITHUB_SETUP_FA.md`
- `ROADMAP_EITAA_NEXT.md`
- `CONTRIBUTING_EITAA_NEXT.md`

راهنمای دقیق Issue/Project/Branch در `GITHUB_SETUP_FA.md` است.

## امنیت

- `.eitaa-next.db` و session file را private نگه دار.
- token، OTP، شماره تلفن، متن خصوصی و capture/HAR را در GitHub public نگذار.
- برای webhook خارج localhost از `--secret` استفاده کن.
- Eitaa غیررسمی/reverse-engineered است؛ رفتار API ممکن است تغییر کند.


## PowerShell و نام کاربری بدون @ (v0.8.1)

در PowerShell بهتر است username را بدون `@` بدهید. eitaa-next آن را خودکار normalize می‌کند:

```powershell
eitaa sync watch rayat_info --once
eitaa sources add medical rayat_info --label "رایات"
eitaa peers resolve rayat_info
```

اگر می‌خواهید `@` را بنویسید، آن را quote کنید: `'@rayat_info'`.
