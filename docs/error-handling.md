# Error handling and retry behavior

The CLI separates protocol failures from presentation. Services raise typed
exceptions, while the command layer converts them into consistent messages with:

- a clear failure category;
- the operation that failed;
- an actionable next step;
- an exact retry delay when Eitaa provides one;
- the original RPC identifier and code for diagnostics.

## OTP request accepted but no code arrives

A successful `auth.sendCode` response means Eitaa accepted the request. It does
not prove that an SMS, app notification, flash call, or voice call reached the
device.

For a successful challenge, the CLI prints the server-provided resend timer:

```text
OTP request accepted by Eitaa.
delivery: sms
next_delivery: call
resend_timeout_seconds: 900
If the OTP does not arrive, do not request another code immediately.
Wait 15 minutes (900 seconds), then use
`eitaa auth resend-code PHONE_NUMBER PHONE_CODE_HASH`.
```

Respect this timer. Sending repeated `auth.sendCode` calls before the cooldown
ends may trigger a longer flood limit.

## OTP request rate-limited

Eitaa may return an RPC identifier such as:

```text
FLOOD_WAIT_125
```

The CLI parses only explicit server-provided wait values and reports:

```text
OTP request temporarily blocked
Eitaa did not allow the CLI to request a new OTP because the request was rate-limited.
Next step: Try again in 2 minutes 5 seconds (125 seconds).
Hint: Do not repeatedly request codes before the cooldown ends; that can extend the limit.
Technical details: RPC FLOOD_WAIT_125 (code 420) method=auth.sendCode
```

The parser also understands explicit prose such as `try again in 60 seconds`
and HTTP `Retry-After` headers. It deliberately does not infer delays from
unrelated digits. For example, `RETRY_LIMIT404` is not treated as a 404-second
cooldown.

When Eitaa reports a flood condition without an exact duration, the CLI says to
try later and explicitly notes that the server did not provide a cooldown. It
does not invent a number.

## OTP-specific failures

The authentication service translates raw RPC strings into stable categories:

| Category | Typical RPC identifiers | CLI action |
|---|---|---|
| Rate limited | `FLOOD_WAIT_*`, `PHONE_NUMBER_FLOOD` | Wait for the exact duration when present. |
| Invalid number | `PHONE_NUMBER_INVALID`, `PHONE_NUMBER_EMPTY` | Use a complete international number. |
| Banned number | `PHONE_NUMBER_BANNED` | Verify in the official client or contact support. |
| Invalid code | `PHONE_CODE_INVALID`, `PHONE_CODE_EMPTY` | Enter the newest code for the active hash. |
| Expired code | `PHONE_CODE_EXPIRED` | Request a new challenge. |
| Invalid challenge | `PHONE_CODE_HASH_INVALID`, `PHONE_CODE_HASH_EXPIRED` | Request a new code and use its new hash. |
| Password required | `SESSION_PASSWORD_NEEDED` | Complete the additional password/SRP step. |
| Restart required | `AUTH_RESTART` | Start again with `auth send-code`. |
| Delivery unavailable | `SEND_CODE_UNAVAILABLE`, `SMS_CODE_CREATE_FAILED` | Wait or use the next advertised method. |

Unknown authentication errors remain available through the original RPC code,
text, and method rather than being hidden behind a generic message.

## General RPC errors

The CLI also gives targeted guidance for:

- administrator or membership permission failures;
- temporary server-side 5xx errors;
- peer-resolution failures;
- missing media files;
- malformed arguments;
- unauthenticated profiles;
- endpoint, DNS, connection, timeout, and HTTP failures.

For non-idempotent operations such as sending a message or creating a group,
do not blindly retry after a transport or server error. First determine whether
the original operation may already have succeeded.

## Python API

All Eitaa exceptions derive from `EitaaError`. OTP failures use `OtpError`:

```python
from eitaa_cli.errors import EitaaError, OtpError, OtpFailureReason

try:
    challenge = await client.auth.request_code("+989121234567")
except OtpError as exc:
    if exc.reason is OtpFailureReason.RATE_LIMITED:
        if exc.retry_after_seconds is not None:
            print(f"Retry after {exc.retry_after_seconds} seconds")
        else:
            print("Rate-limited without an exact server cooldown")
    print(exc.to_dict())
except EitaaError as exc:
    print(exc.to_dict())
```

`to_dict()` returns stable machine-readable fields. `EitaaRPCError` also exposes
`code`, `text`, `method`, `normalized_text`, `retryable`, and
`retry_after_seconds`.

## Retry policy for automation

A safe automation policy is:

1. Never retry an invalid phone number, invalid OTP, expired OTP, invalid hash,
   or permission failure without changing the input or state.
2. For an exact `retry_after_seconds`, schedule one retry after the full delay.
3. For a rate limit without an exact delay, use a conservative backoff and stop
   after a small number of attempts.
4. For transport failures, use bounded exponential backoff with jitter.
5. Never log OTPs, session tokens, or phone-code hashes.
