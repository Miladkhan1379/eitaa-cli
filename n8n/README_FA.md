# اتصال سریع Eitaa Next به n8n

فایل `eitaa-next-webhook-workflow.json` را در n8n از مسیر **Import from File** وارد کنید.

سپس Workflow را فعال کنید و URL production وب‌هوک را بردارید. نمونه:

```powershell
eitaa sync hybrid source:medical --poll 5 --webhook "http://127.0.0.1:5678/webhook/eitaa-next"
```

یا در `automations.json` یک action از نوع `webhook` تعریف کنید.

برای جلوگیری از اجرای دوباره در workflowهای حساس، مقدار `event_id` را به‌عنوان کلید idempotency نگه دارید. اگر `--secret` یا `secret` در action تنظیم شده باشد، امضای HMAC در هدر `X-Eitaa-Signature` ارسال می‌شود.
