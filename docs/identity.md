# Identity & Authentication

From v1.1, the UK Policy Sandbox grows from a single-user tool into a multi-user
platform. This document explains the **identity foundation** introduced in
EPIC-005 — the architecture, not a user guide — and, just as importantly, what
it deliberately does *not* do yet.

> **Scope so far.** Landed:
>
> 1. *Foundation* — provider interfaces, local user store, password hashing,
>    register/authenticate, owner association on saved models (domain layer, no
>    UI).
> 2. *Auth UI & ownership wiring* — a Streamlit account panel
>    (register / sign in / sign out), the signed-in user bound into session
>    state, saved models stamped with the owner, and "my saved models" filtered
>    to the current user (with legacy models preserved).
> 3. *Ownership authorisation* — enforced mutation policy (below).
> 4. *Account self-management* — change password (US-006) and edit profile
>    (US-007): display name and email, with the canonical `user_id` unchanged.
> 5. *Password reset* (US-005) — single-use, time-limited, hashed reset tokens
>    delivered through a pluggable mailer (console for dev, SMTP for deployment).
>
> Still deferred: external OAuth/OIDC, social login, sharing/visibility
> (EPIC-006), leaderboards and encrypted AI keys.

## Why auth is provider-abstracted

The application depends on **interfaces, never on a concrete backend**. The
contract lives in [`model/auth/provider.py`](../model/auth/provider.py):

- `AuthProvider` — the universal surface every backend shares (resolve a user by
  canonical `user_id`, report a `provider_name`).
- `PasswordAuthProvider` — adds email/password `register()` and `authenticate()`.

`LocalAuthProvider` is simply the *first* implementation of
`PasswordAuthProvider`. Because callers depend on the protocol, a future
provider — Authentik/OIDC, Google, Microsoft, GitHub — can be dropped in without
touching the rest of the platform.

Two protocols (not one) exist on purpose: password auth and federated
(authorization-code) auth have fundamentally different flows. Forcing both
through a single `authenticate()` signature would leak one model's assumptions
into the other. A federated provider will implement `AuthProvider` plus its own
redirect/callback protocol when that work lands.

## Why the internal `user_id` is canonical

Every identity has a stable internal `user_id` (a random UUID hex by default).
**Email is never the primary key.**

- Emails change (job moves, typo fixes, provider switches). A canonical key that
  can change is not canonical.
- Owned resources — starting with saved models' `owner_user_id` — reference the
  `user_id`, so changing an email never orphans a user's data.
- Federated providers identify users by their own `sub`/subject. Mapping that to
  our `user_id` (via `provider` + `provider_subject`) lets one internal identity
  later span multiple login methods.

The stored [`User`](../model/auth/types.py) record carries: `user_id`, `email`,
`display_name`, `password_hash` (only for password providers; `None` otherwise),
`created_at`, `updated_at`, `provider`, `provider_subject`, `is_active`.

## Password handling

Passwords are hashed with **Argon2id** via `argon2-cffi`
([`model/auth/password.py`](../model/auth/password.py)). We do **not** roll our
own hashing and never store plaintext. The dependency is pinned, which pins the
hashing parameters; `needs_rehash()` lets a future login transparently upgrade a
still-valid password to stronger parameters without a migration.

`authenticate()` raises the **same** `InvalidCredentialsError` for an unknown
email, a wrong password and an inactive account, so the provider cannot be used
to enumerate which emails are registered.

## How local auth can later be swapped for Authentik/OIDC

1. The local user store is hidden behind the `UserStore` repository interface
   ([`model/auth/user_store.py`](../model/auth/user_store.py)). `JsonUserStore`
   is the first backend; a `SqliteUserStore` / `PostgresUserStore` implementing
   the same interface replaces it with no provider changes.
2. A new `OidcAuthProvider` implements `AuthProvider` (and an OIDC-specific
   redirect/callback protocol), reusing the same `User` record and `user_id`
   space. Existing local accounts are unaffected.
3. Because the app holds only an `AuthProvider` and an `AuthSession`, adding a
   provider is additive — no rewrite of calling code.

## Sessions, and why Streamlit is temporary/constrained

Session state ("who is logged in") is managed by framework-agnostic helpers in
[`model/auth/session.py`](../model/auth/session.py). They operate on any
`MutableMapping`; the app passes Streamlit's `st.session_state`, but the auth
domain imports **no Streamlit**. Only the `AuthSession` principal is stored —
never a password hash.

Streamlit is a deliberately *thin, temporary* host for multi-user behaviour: its
session model is per-browser-session and process-local, with no built-in durable
sessions, CSRF handling or horizontal scale. Keeping all Streamlit-specific code
in the UI layer means the identity layer survives whatever replaces Streamlit as
the platform grows. Any genuinely secure, scalable session/cookie handling is a
later concern and is **not** claimed by this slice.

## Model ownership

Saved models gain an optional `owner_user_id`
([`model/saved_models.py`](../model/saved_models.py)):

- New models can be stamped with the creating user's `user_id`.
- Models created before identity existed — and any created while no user is
  signed in — have `owner_user_id is None` and are treated as **legacy/unowned**.
  Existing saved-model files load unchanged (no schema bump).
- `update` preserves ownership; `clone` inherits the source owner by default and
  can re-own the copy.

### Ownership wiring in the app

`app.py` now stamps ownership and scopes visibility:

- **Saving** stamps the new model with the signed-in user's `user_id`
  (`current_user_id(st.session_state)`); a guest save passes `None` and creates a
  legacy/unowned model.
- **Cloning** gives the copy to the signed-in user (so you own copies you make,
  even of a legacy model); a guest's clone inherits the source owner and stays
  unowned.
- **Visibility** — the saved-models panel lists only what
  `filter_visible_models()` returns for the current viewer.

### Visibility policy (and how legacy access is preserved)

`filter_visible_models(models, viewer_user_id, include_legacy=True)` in
[`model/saved_models.py`](../model/saved_models.py) is the single, Streamlit-free
rule (unit-tested directly):

| Model `owner_user_id` | Signed-in user sees it? | Guest sees it? |
| --- | --- | --- |
| equals the viewer's `user_id` | ✅ | — |
| another user's id | ❌ | ❌ |
| `None` (legacy/unowned) | ✅ (when `include_legacy`) | ✅ (when `include_legacy`) |

**Legacy access is preserved deliberately.** Models created before identity
existed — and anything saved while signed out — have `owner_user_id is None` and
remain visible to *everyone* on the device, signed in or not. This is an explicit
choice so that turning on accounts never hides a user's pre-existing local data.
Legacy models remain **loadable and clonable** by anyone (see the mutation policy
below for why they are *not* editable in place).

### Authorisation: who may mutate a model

Visibility (what you see) and authorisation (what you may change) are separate.
**Filtering is a UX convenience, not the security boundary.** Every in-place
mutation is gated by an explicit, pure policy in
[`model/saved_models.py`](../model/saved_models.py) — `can_mutate()` /
`authorize_mutation()` — which the app calls *before* updating or deleting,
against the model fetched **from the store** (never from the filtered list):

| Model `owner_user_id` | Update / Delete in place | Load (read) | Clone |
| --- | --- | --- | --- |
| equals the actor's `user_id` | ✅ owner only | ✅ | ✅ |
| another user's id | ❌ | ✅* | ✅* |
| `None` (legacy/unowned) | ❌ **read-only** | ✅ | ✅ |
| actor is a guest (`None`) | ❌ (for any owned model) | ✅ | ✅ |

\* In practice the UI filter means a user never selects another user's model;
who may *read/clone* another user's model is a sharing concern (EPIC-006). The
authorisation boundary here governs **mutation**.

**Legacy/unowned models are read-only.** Nobody may update or delete them in
place. A signed-in user *claims* one by **cloning** it — clone never touches the
source and produces a new model owned by the cloner. This combines both options
considered for legacy handling: legacy models can only be cloned, and signing in
lets you claim a copy without overwriting the shared original.

**Enforcement, not filtering.** `ModelAuthorizationError` subclasses
`ModelStoreError` as defence in depth: even a mutation path that forgot to
authorise would fail safe through existing error handling rather than mutating.
In the UI the Update/Delete buttons are disabled when `can_mutate()` is false,
but that is only a hint — the callbacks re-check via `authorize_mutation()`.

Per-owner authorisation of *reads* (restricting who may view/clone another user's
model), roles and admin override are deferred to EPIC-006 and beyond.

## Account self-management

A signed-in user manages their own account from the sidebar **Account settings**
panel, backed by two provider methods (both leave the canonical `user_id`
untouched):

- **Change password** (`change_password`, US-006) — requires the **current**
  password (verified against the stored Argon2id hash), validates the new one and
  re-hashes it. The old password stops working immediately; the session stays
  signed in.
- **Edit profile** (`update_profile`, US-007) — edit **display name** and
  **email**. Email is normalised and must stay unique (the store rejects a
  clash). Changing the email changes the *login identifier* but **not** the
  `user_id`, which is exactly why identity is keyed on an internal id — see
  *Why the internal `user_id` is canonical* above. The in-session principal is
  refreshed after a successful edit.

These are domain-layer methods on `LocalAuthProvider` (Streamlit-free); the
sidebar forms only collect input and call them.

## Forgotten-password reset (US-005)

A user who cannot sign in requests a reset by email; they receive a single-use,
time-limited link and choose a new password. Two provider methods drive it,
both Streamlit-free:

- **`request_password_reset(email)`** — issues a token and emails a link.
- **`reset_password(token, new_password)`** — validates the token and sets the
  new password.

### Security properties

- **Tokens are hashed at rest.** The raw token (256 bits from
  `secrets.token_urlsafe`) goes only in the email/link; the store keeps just its
  SHA-256 (`model/auth/tokens.py`). A leaked token store cannot be used to reset
  anyone's password. SHA-256 (not Argon2id) is correct here precisely *because*
  the token is high-entropy — the slow KDF is for low-entropy passwords.
- **Single-use.** On completion, all of the user's reset tokens are deleted, so
  a link cannot be replayed. Requesting a new link invalidates any previous one.
- **Time-limited.** Tokens carry an `expires_at` (default 1 hour); expired
  tokens are rejected.
- **Old password invalidated.** Completing a reset re-hashes the password, so the
  previous one immediately stops working.
- **Anti-enumeration.** `request_password_reset` does the same observable work
  and returns nothing whether or not the email is registered; the UI always shows
  the same "if an account exists…" message.
- **Uniform failure.** Unknown, used and expired tokens all raise the same
  `InvalidResetTokenError`.

### Email delivery is pluggable (and SMTP is a deployment concern)

Delivery is hidden behind the `Mailer` protocol (`model/auth/email.py`), mirroring
the auth-provider abstraction:

- **`ConsoleMailer`** — the safe default when no SMTP server is configured (local
  / dev): it prints the reset link to the **server console** so the flow is fully
  exercisable offline. Read the console to get the link.
- **`SmtpMailer`** — sends real email over SMTP (STARTTLS), wired in at deployment.

`app.py` chooses between them by configuration: if `SMTP_HOST` is set it builds an
`SmtpMailer` from env vars (`SMTP_PORT`, `SMTP_SENDER`, `SMTP_USERNAME`,
`SMTP_PASSWORD`, `SMTP_USE_TLS`, `APP_BASE_URL`); otherwise it uses the
`ConsoleMailer`. A live deployment is expected to provide an SMTP server. The
reset link is a normal app URL carrying the token as a query parameter
(`…/?reset_token=…`); opening it shows the "set a new password" form.

## Where data lives

- Local users: `users.json` (default app dir). It contains **password hashes**,
  so it is runtime data/secrets — **gitignored**, never committed (alongside
  `saved_models.json`).
- Reset tokens: `reset_tokens.json` (default app dir). It holds **token hashes**
  and is likewise runtime secrets data — **gitignored**.
- Versioned schemas (`AUTH_SCHEMA_VERSION`, `RESET_TOKENS_SCHEMA_VERSION`);
  validate-on-read; atomic temp-file writes — the same contract as the
  saved-models store.

## Deferred (later epics)

External OAuth/OIDC · social login · sharing & visibility (EPIC-006) ·
leaderboards (EPIC-007) · encrypted per-user AI keys (EPIC-009) ·
durable/secure session & cookie handling at scale.
