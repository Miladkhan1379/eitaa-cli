# Authentication and OTP delivery

Eitaa authentication uses the layer-135 methods `auth.sendCode`,
`auth.resendCode`, `auth.signIn`, and, when registration is required,
`auth.signUp`.

## Important delivery rule

The client can describe its capabilities, but **Eitaa's server chooses the
actual OTP channel**. The supplied browser capture used a zero-flag
`codeSettings` request and Eitaa returned:

- current delivery: `auth.sentCodeTypeSms`;
- next delivery: `auth.codeTypeCall`;
- a server-defined resend timeout.

Accordingly, the CLI treats SMS as the default preference without claiming it
can force SMS for every account, number, region, or rate-limit state.

## Supported OTP forms

Run:

```bash
eitaa auth methods
```

The bundled schema represents four delivery forms:

| CLI name | TL response | Behavior |
|---|---|---|
| `sms` | `auth.sentCodeTypeSms` | A numeric code is sent by SMS. |
| `call` | `auth.sentCodeTypeCall` | A voice call reads the numeric code. |
| `flash-call` | `auth.sentCodeTypeFlashCall` | The caller ID is matched against a server pattern. |
| `app` | `auth.sentCodeTypeApp` | The code is delivered inside an already authorized Eitaa app. |

The `next_type` field may advertise SMS, call, or flash-call as the next resend
method. In-app delivery is selected by the server when an existing authorized
app is suitable.

## Standard SMS-first login

```bash
eitaa auth login +989121234567
```

This is equivalent to an SMS preference:

```bash
eitaa auth login +989121234567 --delivery sms
```

The command prints the **actual** delivery method, code length, next delivery,
and resend timeout before prompting for the code.

Avoid passing OTPs on the command line when possible. Command-line arguments may
be visible in shell history or process listings.

## Separate request and sign-in

Use separate commands when an automation or UI needs to control each step:

```bash
# 1. Request the initial challenge
eitaa auth send-code +989121234567 --delivery sms

# 2. Enter the returned hash and OTP without requesting another code
eitaa auth login +989121234567 \
  --phone-code-hash 'RETURNED_PHONE_CODE_HASH'
```

For machine-readable integration:

```bash
eitaa auth send-code +989121234567 --json
```

The JSON includes:

```json
{
  "phone_number": "989121234567",
  "phone_code_hash": "...",
  "delivery": "sms",
  "next_delivery": "call",
  "timeout_seconds": 900,
  "code_length": 5,
  "flash_call_pattern": null,
  "raw": {}
}
```

Treat `phone_code_hash` as temporary sensitive authentication state. It is tied
to the corresponding request and should not be logged or reused indefinitely.

## Voice-call fallback

When the first response advertises `next_delivery: call`, wait for the
server-provided timeout, then request the next method:

```bash
eitaa auth resend-code \
  +989121234567 \
  'CURRENT_PHONE_CODE_HASH' \
  --preferred call
```

Use the new hash returned by `resend-code`:

```bash
eitaa auth login +989121234567 \
  --phone-code-hash 'NEW_PHONE_CODE_HASH'
```

Calling `resend-code` too early may produce an RPC error or rate-limit response.
The CLI does not sleep automatically for long server timeouts.

## Flash-call capability

Flash-call verification requires a phone/device environment that can observe an
incoming caller ID. A terminal-only client normally cannot read the phone's call
log automatically, but it can advertise protocol support:

```bash
eitaa auth send-code +989121234567 \
  --allow-flash-call \
  --current-number
```

`--current-number` is rejected unless `--allow-flash-call` is also present.
When Eitaa selects flash-call, the response includes `flash_call_pattern`. The
user must obtain the matching digits from the incoming caller ID and submit the
code through `auth login --phone-code-hash ...`.

## Application hash capability

`--allow-app-hash` sets the layer-135 `allow_app_hash` capability flag:

```bash
eitaa auth send-code +989121234567 --allow-app-hash
```

This is not a request for in-app delivery. It permits compatible SMS payloads to
contain an application hash used by supported mobile-app code retrieval flows.
A general Python terminal application does not automatically consume that hash.

## Signup-required accounts

`auth login` detects `auth.authorizationSignUpRequired` and prompts for a first
name:

```bash
eitaa auth login +989121234567 \
  --first-name Ali \
  --last-name Example
```

The explicit form is:

```bash
eitaa auth signup +989121234567 Ali Example
```

A challenge created by `send-code` or `resend-code` can be reused with
`--phone-code-hash`.

## Python API

```python
from eitaa_cli import EitaaClient
from eitaa_cli.models import OtpCodeSettings, OtpDeliveryMethod

client = await EitaaClient.create(require_auth=False)

async with client:
    challenge = await client.auth.request_code(
        "+989121234567",
        settings=OtpCodeSettings(),
    )

    assert challenge.delivery in {
        OtpDeliveryMethod.SMS,
        OtpDeliveryMethod.CALL,
        OtpDeliveryMethod.FLASH_CALL,
        OtpDeliveryMethod.APP,
        OtpDeliveryMethod.UNKNOWN,
    }

    authorization = await client.auth.sign_in(
        challenge.phone_number,
        challenge.phone_code_hash,
        input("OTP: "),
    )
```

To request the advertised fallback:

```python
fallback = await client.auth.resend_code(
    challenge.phone_number,
    challenge.phone_code_hash,
)
```

## Common OTP errors

- **The code is invalid:** ensure it belongs to the current `phone_code_hash`.
- **The code expired:** request a new challenge instead of reusing an old hash.
- **A call arrived instead of SMS:** Eitaa selected the channel; inspect
  `delivery` and use the code from that method.
- **Resend is rejected:** wait for `timeout_seconds` and avoid repeated retries.
- **Password/SRP is required:** password-protected login is still a deliberate
  high-level gap; the schema methods remain available for future implementation.

## Delivery confirmation and resend timing

A returned `auth.sentCode` challenge confirms that Eitaa accepted the OTP
request. It does **not** confirm that the SMS or call reached the phone. The CLI
therefore prints the exact `timeout_seconds` value in both human-readable and
raw seconds form.

When the code does not arrive, wait for the printed duration before running
`auth resend-code`. For example, a timeout of `125` is displayed as
`2 minutes 5 seconds (125 seconds)`.

Do not repeatedly run `auth send-code` during this period. Repeated requests can
trigger a flood limit or extend an existing cooldown.

## Structured OTP errors

Raw Eitaa errors are translated into typed `OtpError` values. The CLI provides
specific guidance for rate limits, invalid or banned phone numbers, invalid or
expired codes, invalid challenge hashes, password requirements, authentication
restarts, and delivery failures.

When Eitaa returns an exact wait identifier such as `FLOOD_WAIT_90`, the CLI
prints `Try again in 1 minute 30 seconds (90 seconds)`. When no exact duration is
provided, the CLI says so instead of inventing a retry time.

See [Error handling and retry behavior](error-handling.md) for the complete
mapping and Python API examples.
