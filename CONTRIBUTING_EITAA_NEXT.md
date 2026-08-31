# Contributing to this eitaa-cli fork

- Keep `main` usable; work on focused branches.
- Add a regression test before or with every bug fix.
- Do not assume Telegram behavior equals Eitaa behavior. Mark protocol assumptions and verify them on Eitaa.
- Preserve upstream compatibility where practical.
- Never commit session tokens, OTPs, phone numbers, private messages, HAR files, browser captures, or secrets.
- Prefer stable typed peer references for background jobs.
- Do not automatically retry non-idempotent send operations unless idempotency/success state is known.
- Run `pytest -q`, Ruff and mypy before merge.
