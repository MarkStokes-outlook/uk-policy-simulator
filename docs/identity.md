# Identity & Authentication

From v1.1, the UK Policy Sandbox grows from a single-user tool into a multi-user
platform. This document explains the **identity foundation** introduced in
EPIC-005 — the architecture, not a user guide — and, just as importantly, what
it deliberately does *not* do yet.

> **Scope so far.** Two slices have landed:
>
> 1. *Foundation* — provider interfaces, local user store, password hashing,
>    register/authenticate, owner association on saved models (domain layer, no
>    UI).
> 2. *Auth UI & ownership wiring* — a Streamlit account panel
>    (register / sign in / sign out), the signed-in user bound into session
>    state, saved models stamped with the owner, and "my saved models" filtered
>    to the current user (with legacy models preserved).
>
> Still deferred: password reset email, external OAuth/OIDC, social login, the
> full profile screen, sharing/visibility (EPIC-006), leaderboards and encrypted
> AI keys.

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
Legacy models therefore behave like the shared, single-user store did before
v1.1; they remain loadable, updatable and clonable. Per-owner *authorisation*
(restricting who may edit/delete someone else's model) is a sharing/visibility
concern deferred to EPIC-006.

## Where data lives

- Local users: `users.json` (default app dir). It contains **password hashes**,
  so it is runtime data/secrets — **gitignored**, never committed (alongside
  `saved_models.json`).
- Versioned schema (`AUTH_SCHEMA_VERSION`); validate-on-read; atomic temp-file
  writes — the same contract as the saved-models store.

## Deferred (not in this slice)

Password reset email flow · external OAuth/OIDC · social login · full profile UI ·
per-owner authorisation of edit/delete (legacy & cross-user) · sharing &
visibility (EPIC-006) · leaderboards (EPIC-007) · encrypted per-user AI keys
(EPIC-009) · durable/secure session & cookie handling at scale.
