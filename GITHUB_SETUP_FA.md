# تنظیم GitHub برای eitaa-next

این فایل برای fork خودت است. هدف این است که `main` همیشه نسخه نسبتاً پایدار باشد و هر قابلیت روی branch جدا ساخته شود.

## Branch پیشنهادی برای v0.8

```text
feature/eitaa-next-v0.8
```

بعد از نصب بسته و سبز شدن تست‌ها:

```powershell
git status
git add .
git commit -m "feat: add eitaa-next v0.8 source registry and readable CLI"
git push -u origin feature/eitaa-next-v0.8
```

بعد در GitHub یک Pull Request از `feature/eitaa-next-v0.8` به `main` **همان fork خودت** بساز.

## Labels پیشنهادی

این Labelها را در `Issues > Labels` بساز:

- `priority:P0` — خرابی/ریسک از دست دادن پیام یا اتوماسیون
- `priority:P1` — قابلیت مهم نسخه بعد
- `priority:P2` — بهبود مهم ولی غیرفوری
- `priority:P3` — ایده/پولیش
- `protocol` — رفتار reverse-engineered ایتا
- `needs-testing` — نیازمند تست روی اکانت واقعی
- `sync`
- `automation`
- `n8n`
- `cli-ui`
- `media`
- `peer`
- `windows`

## Project Board

از Profile > Projects یک Project با نام زیر بساز:

```text
Eitaa Next
```

Board ساده و کافی:

```text
Backlog | Ready | In progress | Testing | Done
```

فیلدهای اختیاری مفید:

- Priority: P0/P1/P2/P3
- Area: Protocol / Sync / Automation / Media / CLI / Auth
- Target: v0.8 / v0.9 / Later

## Issueهای پیشنهادی بعد از v0.8

### 1. P0 — Validate low-latency update engine

Title:

```text
protocol: validate updates.getState/getDifference for low-latency events
```

هدف: رفتار `updates.getState` و `updates.getDifference` روی اکانت واقعی بررسی شود و اگر پایدار بود، polling به حالت hybrid ارتقا پیدا کند.

Labels: `priority:P0`, `protocol`, `sync`, `needs-testing`

### 2. P1 — Linux service/daemon

```text
feat: add systemd service templates for sync and automation
```

Labels: `priority:P1`, `automation`, `n8n`

### 3. P1 — Media download filters/resume

```text
feat: add filtered and resumable bulk media downloads
```

Labels: `priority:P1`, `media`

### 4. P1 — Source discovery/import

```text
feat: import selected channels and groups into the source registry
```

Labels: `priority:P1`, `peer`, `cli-ui`

### 5. P2 — Automation editor

```text
feat: add interactive automation rule wizard
```

Labels: `priority:P2`, `automation`, `cli-ui`

### 6. P2 — Local management dashboard

```text
feat: add local web dashboard for sources, rules, status and failures
```

Labels: `priority:P2`, `cli-ui`, `automation`

## Milestones

اگر Milestone استفاده می‌کنی:

- `v0.8 — Usability & source registry`
- `v0.9 — Low latency & daemon`
- `v1.0 — Stable automation platform`

## قانون Merge

قبل از Merge هر PR:

```powershell
python -m compileall -q src\eitaa_cli
pytest -q
```

و برای تغییرات پروتکل/Sync حداقل یک smoke test واقعی روی اکانت خودت انجام بده، بدون اینکه token/OTP/شماره تلفن یا متن خصوصی را داخل Issue یا log عمومی بگذاری.
