# HTTP compatibility profile

## Purpose

The supplied Eitaa browser capture uses binary HTTPS POST requests with browser
request metadata. The client applies one stable compatibility profile so it
does not accidentally identify requests with package, runtime, or HTTP-library
branding.

The default outbound metadata includes:

```text
Accept: */*
Accept-Language: en,de-DE;q=0.9,en-US;q=0.8
Origin: https://web.eitaa.com
Sec-GPC: 1
Sec-Fetch-Dest: empty
Sec-Fetch-Mode: cors
Sec-Fetch-Site: cross-site
User-Agent: Mozilla/5.0 ... Firefox/152.0
```

There is no default `eitaa-cli`, `Python`, package-version, or `httpx` marker in
request headers or signup application metadata. HTTP/2 is enabled by default.

## Stable rather than rotating

`WebClientProfile` is immutable and stable for the lifetime of a client. The
implementation does not rotate user agents, synthesize random browser versions,
or attempt to reproduce TLS or JavaScript fingerprints. This avoids brittle
anti-detection behavior and makes captured-protocol compatibility reproducible.

A header profile alone cannot make a non-browser transport indistinguishable
from a browser. TLS implementation, HTTP/2 framing, connection behavior, and
server-side policy may still differ. The project makes no guarantee that a
server will classify the client as a browser.

## Configuration

The compatibility fields can be overridden when a reviewed Eitaa web build
changes:

```bash
export EITAA_WEB_USER_AGENT='Mozilla/5.0 ...'
export EITAA_WEB_ACCEPT_LANGUAGE='en-US,en;q=0.9'
export EITAA_WEB_ORIGIN='https://web.eitaa.com'
export EITAA_WEB_SYSTEM_VERSION='Linux x86_64'
export EITAA_WEB_LANGUAGE_CODE='en'
export EITAA_HTTP2=true
```

Prefer updating all related fields together from a verified browser capture.
Do not put account tokens, OTP values, or phone-code hashes in environment
variables used for request-profile configuration.

## Signup metadata

`auth.signUp` uses the same typed application-information shape observed in the
supplied client:

```text
eitaaAppInfo
  build_version: 2496
  device_model: <configured browser user agent>
  system_version: Linux x86_64
  app_version: 4.6.12 K
  lang_code: en
  sign: ""
```

The values are centralized in `WebClientProfile` and `EitaaSettings`; service
code does not construct ad hoc identifying strings.

## Tests

The release test suite verifies that default headers and signup metadata do not
contain these markers:

```text
eitaa-cli
python
httpx
```

It also verifies that HTTP/2 remains enabled by default.
