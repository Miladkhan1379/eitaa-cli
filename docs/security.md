# Security model

The saved Eitaa token is a bearer credential. Anyone who obtains it may be able
to act as the account until the token is invalidated or expires.

## Session store protections

The default store is `~/.config/eitaa-cli/sessions.json`. The implementation:

- supports multiple named profiles;
- writes through a temporary file and atomic replacement;
- sets temporary and final files to owner read/write only (`0600`);
- does not print the token in normal status output.

These controls reduce accidental exposure but do not replace host security or
secret-management policy.

## Recommended practices

1. Keep session files outside cloud-synchronized and public directories.
2. Never commit tokens, OTPs, HAR files, access hashes, or private messages.
3. Use a dedicated automation account with minimum required permissions.
4. Keep confirmation prompts enabled for interactive use.
5. Use deterministic typed peer references in unattended jobs.
6. Apply conservative send rates and honor server rate limits.
7. Restrict filesystem access to the account running the automation.
8. Avoid placing OTPs, `phone_code_hash` values, or tokens in shell history,
   process arguments, logs, or CI variables visible to untrusted users.
9. Treat global/public search results as potentially sensitive output; do not
   persist private message text unnecessarily.
10. Prefer `auth logout` over `--local-only` when retiring a session.

## Threat boundaries

The CLI does not bypass OTP, password/SRP, account permissions, group/channel
roles, bans, rate limits, or server-side policy. It sends ordinary API calls under
the authenticated account's authority.

## Captures and debugging

HAR files can contain:

- session tokens;
- phone numbers and account metadata;
- peer IDs and access hashes;
- message contents;
- media locations;
- invite hashes.

Sanitize captures before sharing and prefer minimal encoded fixtures. The private
capture regression test is opt-in and the distributable artifacts exclude HARs.
