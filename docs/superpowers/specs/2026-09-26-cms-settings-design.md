# CMS Settings: Checkout Configuration and Maintenance Mode

## Status

Design approved conversationally on 2026-09-26. Implementation starts after
this document is reviewed.

## Goal

Extend `/cms/settings` with the two operational controls that are most useful
to the TC Mudah team:

1. Payment and checkout information currently read from backend environment
   variables.
2. A maintenance switch and message for temporarily pausing participant-facing
   flows while staff retain access to the CMS.

The existing registration visibility setting must keep working unchanged.

## Current Context

- `public.app_settings` already stores string key/value pairs and has a unique
  key index.
- `GET /checkout/info` currently returns `BANK_NAME`, `BANK_ACCOUNT`,
  `BANK_HOLDER`, and `GROUP_LINK` from `app/core/config.py`.
- The CMS settings page reads and writes the existing generic settings routes.
- Public frontend code reads `disable_daftar_kelas` and its message without
  authentication.
- There is no Next.js middleware or global maintenance gate today.

## User-facing behavior

### Payment settings

The CMS settings page gets a new “Pembayaran” section with four fields:

- Nama bank
- Nomor rekening
- Nama pemilik rekening
- Link grup WhatsApp

Saving the section writes the values to the database. New checkout requests
read the database values, so an admin can change payment details without a
backend redeploy.

### Maintenance mode

The CMS settings page gets a “Maintenance” section with:

- A toggle.
- An editable message.

When enabled, public and participant-facing pages show a simple maintenance
screen using the configured message. `/cms` and authentication pages remain
available so staff can log in and turn the mode off. The frontend refreshes the
state on navigation/focus and periodically, so an admin change takes effect
without a full deployment.

Participant checkout and payment-upload API calls are rejected while
maintenance is enabled. Staff API calls remain available. Catalog reads can
remain available because the frontend gate hides the participant flow and this
keeps the public site lightweight if a visitor has a stale page open.

## Settings keys

The existing `app_settings` table is reused; no new table is needed.

| Key | Visibility | Default/fallback | Meaning |
| --- | --- | --- | --- |
| `checkout_bank_name` | admin | `BANK_NAME` during migration | Bank display name |
| `checkout_bank_account` | admin | `BANK_ACCOUNT` during migration | Account number |
| `checkout_bank_holder` | admin | `BANK_HOLDER` during migration | Account holder |
| `checkout_group_link` | admin | `GROUP_LINK` during migration | Optional WhatsApp group URL |
| `maintenance_mode` | public read, admin write | `false` | Whether participant UI is paused |
| `maintenance_message` | public read, admin write | `Situs sedang dalam maintenance. Silakan coba lagi nanti.` | Message shown to participants |

The existing `disable_daftar_kelas` and `disabled_daftar_kelas_msg` keys remain
public-read settings. Public reads are allowlisted; arbitrary private keys must
not become readable through the unauthenticated settings endpoint.

## Backend design

### Settings access

- Keep `GET /settings` for public allowlisted keys used by the navbar,
  registration page, and maintenance gate.
- Add `GET /admin/settings` requiring `admin` or `superadmin` for the CMS form.
- Keep `PUT /settings/{key}` for admins, but validate keys and values with a
  per-key allowlist instead of accepting arbitrary database keys.
- The admin read response returns effective values (database value first,
  migration fallback second) so the CMS can display existing env values before
  they are saved to the database.

### Checkout resolution

`/checkout/info` uses one settings read for the four `checkout_*` keys. A
database value wins. During the migration window, a missing key falls back to
the corresponding environment variable. Once all four values have been saved
through the CMS and verified, the environment variables and their config fields
can be removed in a cleanup deploy.

If a required payment value is missing after the fallback is removed, the
endpoint returns a clear service-unavailable error instead of returning a
partially configured checkout payload.

### Maintenance resolution

Add a small settings helper used by both the settings router and orders router
to read the maintenance keys in one query. The helper parses the boolean value
strictly (`true`/`false`) and applies the default message when the message is
empty.

The order creation and payment-upload-intent handlers call the helper after
authentication and reject non-staff users with a 503-style application error
when maintenance is active. Existing admin order approval/management routes do
not use this guard.

## Frontend design

- Extend `src/app/cms/settings/page.tsx` with separate Registration,
  Pembayaran, and Maintenance cards.
- Show the Settings navigation item and page controls only to `admin` and
  `superadmin`; mentors should not receive a settings-page request that they
  cannot update.
- Load public registration/maintenance values through the public settings route
  and payment values through `/admin/settings`.
- Save payment fields in one request per field or one explicit section action,
  keeping the existing loading and success/error modal behavior.
- Add a client `MaintenanceGate` mounted from the root layout. It reads the
  public maintenance settings with `cache: "no-store"`, skips `/cms` and auth
  routes, and renders the maintenance screen when active. Request failures do
  not lock the application; the existing page remains usable.
- Keep checkout response types unchanged (`bank_name`, `bank_account`,
  `bank_holder`, `group_link`) so the checkout UI does not need a data-shape
  migration.

## Migration and environment cleanup

The first implementation deploy is deliberately backward-compatible:

1. Deploy database-backed settings with env fallback.
2. Open `/cms/settings`, confirm the four payment values, and save them.
3. Verify `/checkout/info`, a checkout preview, and maintenance on/off behavior.
4. Remove `BANK_NAME`, `BANK_ACCOUNT`, `BANK_HOLDER`, and `GROUP_LINK` from
   the deployment environment, `Settings`, `.env.example`, and README in a
   follow-up cleanup change.

This ordering avoids losing the current payment destination if the deployment
does not yet contain the new database rows. Maintenance has no environment
dependency and defaults to off.

## Validation and error handling

- Trim all text values before persistence.
- Require non-empty bank name, account, and holder values.
- Allow an empty group link, but reject malformed non-empty URLs.
- Limit maintenance message and text fields to practical lengths before the
  database write.
- Keep all settings writes restricted to `admin` and `superadmin`.
- Surface backend validation errors in the existing CMS error modal.

## Testing strategy

Backend tests must cover:

- Public settings allowlist and denial of private checkout keys.
- Admin settings read/write authorization and validation.
- Checkout info preferring database values and using env fallback when a row is
  absent.
- Checkout/payment upload rejection for participants during maintenance and
  continued staff access.
- Existing registration settings behavior remains green.

Frontend verification must include TypeScript/build and Biome checks. The
maintenance gate should be checked for CMS/auth route bypass and participant
screen rendering, with request failure leaving the normal page usable.

## Non-goals

- Moving infrastructure settings (JWT, database pool, upload limits) into CMS.
- Moving active batch, class visibility, package visibility, or material
  visibility into global settings.
- Adding a new settings table or a general-purpose arbitrary configuration
  editor.
