# Quick Start v0.9

```powershell
# 1) نصب
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install-eitaa-next.ps1 "D:\milad\Project\eitaa-cli\eitaa-cli"

# 2) تست
cd D:\milad\Project\eitaa-cli\eitaa-cli
.venv\Scripts\Activate.ps1
pytest -q

# 3) انتخاب تعاملی کانال
eitaa sources pick medical --kind channel

# 4) Hybrid watch
eitaa sync hybrid source:medical --poll 5

# 5) دانلود گروهی
eitaa downloads run source:medical --type video --limit 1000 -o .\downloads

# 6) پنل وب
eitaa web start

# 7) چند اکانت
eitaa accounts list
eitaa fleet watch source:medical --profile work --profile personal

# 8) اجرای دائمی Windows
eitaa service windows source:medical --install
```
