# CMS Settings: Checkout Configuration and Maintenance Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add database-backed payment settings and a participant-facing maintenance mode to `/cms/settings`, while preserving a safe environment-variable migration path.

**Architecture:** Keep the existing `app_settings` key/value table, but place all setting resolution and allowlists in one backend service. Public settings remain restricted to an explicit allowlist; admin reads use a protected route. Checkout reads database values first with a temporary env fallback, while a client-side maintenance gate and server-side checkout guards pause participant flows.

**Tech Stack:** FastAPI, Pydantic, Supabase/PostgREST, pytest, Next.js 15 App Router, React 19, TypeScript, Tailwind CSS, Biome.

**Spec:** `tcmudahbe/docs/superpowers/specs/2026-09-26-cms-settings-design.md`

## Global Constraints

- The existing `public.app_settings` table is reused; no new table is needed.
- Public reads are allowlisted; arbitrary private keys must not become readable through the unauthenticated settings endpoint.
- `/cms` and authentication pages remain available while maintenance is enabled.
- Participant checkout and payment-upload API calls are rejected while maintenance is enabled; staff API calls remain available.
- Database values win over env fallback during migration.
- Required payment values are bank name, account, and holder; group link may be empty.
- Settings writes remain restricted to `admin` and `superadmin`.
- Do not move JWT, database pool, upload limits, batch, catalog visibility, or material visibility into the global settings editor.

## Review Focus

1. A public request for `checkout_bank_account` must be rejected instead of leaking private admin settings; covered by `test_public_settings_reject_private_key` in Task 1.
2. A missing database payment row must still serve the current env value during migration, while a database row overrides it; covered by `test_checkout_info_prefers_database_value_and_falls_back_to_env` in Task 2.
3. Maintenance must block participant upload/order actions but leave staff actions available; covered by `test_payment_upload_intent_is_blocked_for_participant_during_maintenance` and `test_staff_can_upload_during_maintenance` in Task 2.
4. An invalid payment URL or blank required payment field must produce a validation error without an upsert; covered by `test_setting_write_validates_checkout_values` in Task 1.
5. A settings request failure must not trap the frontend behind maintenance, and CMS/auth routes must bypass the gate; covered by the `MaintenanceGate` route-state checks in Task 4 plus the production build check in Task 5.

---

### Task 1: Centralize setting resolution and protect settings routes

**Files:**
- Create: `tcmudahbe/app/services/app_settings.py`
- Modify: `tcmudahbe/app/routers/settings.py`
- Modify: `tcmudahbe/app/main.py`
- Modify: `tcmudahbe/app/schemas/schemas.py` only if a typed admin settings response is needed
- Test: `tcmudahbe/tests/routers/test_settings.py`
- Modify: `tcmudahbe/tests/conftest.py` to patch the new service Supabase/config dependencies

**Interfaces:**
- Produces `PUBLIC_SETTING_KEYS`, `ADMIN_SETTING_KEYS`, `read_setting_values(keys: Sequence[str]) -> dict[str, str]`, `effective_checkout_values() -> dict[str, str]`, `maintenance_state() -> tuple[bool, str]`, and `validate_setting_value(key: str, value: str) -> str` for later tasks.
- Produces `GET /admin/settings?keys=...` protected by `require_roles("admin", "superadmin")`.
- Keeps `GET /settings` and `GET /settings/{key}` public only for the explicit public allowlist.
- Keeps `PUT /settings/{key}` at the existing URL, with admin authorization and per-key validation.

- [ ] **Step 1: Write failing route/service tests**

  Add tests for:

  - `GET /settings?keys=maintenance_mode&keys=maintenance_message` returning the requested public values/defaults.
  - `GET /settings?keys=checkout_bank_account` returning a 400/403 response and performing no database read for a private key.
  - `GET /admin/settings?keys=checkout_bank_name` returning an effective env fallback for an admin and rejecting an unauthenticated request.
  - `PUT /settings/maintenance_mode` accepting only `true`/`false`.
  - `PUT /settings/checkout_bank_name` rejecting an empty value and `checkout_group_link` rejecting a malformed non-empty URL without calling `upsert`.
  - An allowed write using `maintenance_mode` still performs exactly one upsert, updating the existing test that currently uses the arbitrary key `feature`.

- [ ] **Step 2: Run the focused tests and verify the expected RED failures**

  Run from `tcmudahbe`:

  ```powershell
  pytest tests/routers/test_settings.py -v
  ```

  Expected: failures because the admin route, allowlist, and validation service do not exist yet.

- [ ] **Step 3: Implement `app/services/app_settings.py`**

  Define the public/admin key sets, defaults, env fallback map, one-query Supabase reader, strict boolean/message parsing, checkout resolution, and per-key validation. Keep the Supabase client and config access in this service so routers only coordinate HTTP concerns.

- [ ] **Step 4: Implement the protected admin settings router and public allowlist**

  Add a second router with prefix `/admin/settings`, include it from `app/main.py`, route CMS reads through it, and update existing public/single-key routes to reject unknown/private keys. Preserve the current response shape for public setting reads and `AppSettingOut` writes.

- [ ] **Step 5: Run the focused tests and verify GREEN**

  ```powershell
  pytest tests/routers/test_settings.py tests/routers/test_perf_11_15_routes.py -v
  ```

  Expected: all settings tests pass, including the existing one-query and upsert assertions.

- [ ] **Step 6: Commit the backend settings boundary**

  ```powershell
  git add app/services/app_settings.py app/routers/settings.py app/main.py app/schemas/schemas.py tests/routers/test_settings.py tests/routers/test_perf_11_15_routes.py tests/conftest.py
  git commit -m "feat: centralize and protect app settings"
  ```

### Task 2: Move checkout resolution to database and enforce maintenance on participant payment flows

**Files:**
- Modify: `tcmudahbe/app/routers/orders.py`
- Modify: `tcmudahbe/app/core/config.py` only to keep the four env fields as transitional fallback sources
- Test: `tcmudahbe/tests/routers/test_checkout_settings.py`

**Interfaces:**
- Consumes `effective_checkout_values()` and `maintenance_state()` from Task 1.
- Produces unchanged `CheckoutInfoOut` fields: `bank_name`, `bank_account`, `bank_holder`, and optional `group_link`.
- Adds a small internal guard `ensure_participant_flow_available(user: dict) -> None` used by upload-intent and order creation.

- [ ] **Step 1: Write failing checkout and maintenance tests**

  Add tests for:

  - `/checkout/info` returning database values when all four `checkout_*` rows exist.
  - `/checkout/info` returning patched `BANK_*`/`GROUP_LINK` values when rows are absent.
  - `/checkout/info` returning 503 with a clear configuration message when required values are absent from both sources.
  - Participant `/orders/upload-intent` returning 503 and not invoking CRUD while `maintenance_mode=true`.
  - Participant order creation returning 503 while maintenance is enabled.
  - Admin/staff upload-intent remaining available while maintenance is enabled.

- [ ] **Step 2: Run the focused tests and verify RED**

  ```powershell
  pytest tests/routers/test_checkout_settings.py -v
  ```

  Expected: failures because checkout still reads module-level env values and no maintenance guard exists.

- [ ] **Step 3: Implement database-first checkout info**

  Replace the direct `settings.BANK_*` reads in `/checkout/info` with `effective_checkout_values()`. Change the transitional `BANK_*`/`GROUP_LINK` config defaults to empty strings so an absent env value cannot masquerade as a real payment destination. Raise `ServiceUnavailableError("Informasi pembayaran belum dikonfigurasi")` when required values are empty; keep the response schema and frontend payload unchanged.

- [ ] **Step 4: Implement the participant maintenance guard**

  Call `maintenance_state()` after authentication in `create_payment_upload_intent` and `create_order`. Treat `mentor`, `admin`, and `superadmin` as staff; reject other roles only when the mode is active. Leave admin order review/status routes untouched.

- [ ] **Step 5: Run the focused tests and verify GREEN**

  ```powershell
  pytest tests/routers/test_checkout_settings.py tests/routers/test_perf_11_15_routes.py -v
  ```

  Expected: checkout precedence, fallback, missing-config, maintenance rejection, and staff bypass tests pass.

- [ ] **Step 6: Commit checkout and maintenance enforcement**

  ```powershell
  git add app/routers/orders.py app/core/config.py tests/routers/test_checkout_settings.py
  git commit -m "feat: use app settings for checkout and maintenance guards"
  ```

### Task 3: Add the CMS payment and maintenance controls

**Files:**
- Create: `TCMudahFE/lib/settings.ts`
- Create: `TCMudahFE/src/app/cms/settings/settings-api-contract.test.ts`
- Modify: `TCMudahFE/src/app/cms/settings/page.tsx`
- Modify: `TCMudahFE/src/app/cms/components/CMSLayoutClient.tsx`

**Interfaces:**
- `TCMudahFE/lib/settings.ts` exports `fetchPublicSettings(keys: string[])`, `fetchAdminSettings(keys: string[])`, and `updateSetting(key: string, value: string)` using same-origin `/api` requests and credentials.
- The CMS page consumes keys `disable_daftar_kelas`, `disabled_daftar_kelas_msg`, `checkout_bank_name`, `checkout_bank_account`, `checkout_bank_holder`, `checkout_group_link`, `maintenance_mode`, and `maintenance_message`.
- Settings navigation and controls are available only to `admin` and `superadmin`.

- [ ] **Step 1: Add the failing API helper contract check**

  Create `TCMudahFE/src/app/cms/settings/settings-api-contract.test.ts` with typed calls to the three helpers and assertions on their promise shapes. Run `npx tsc --noEmit` and confirm it fails because `lib/settings.ts` is missing.

- [ ] **Step 2: Implement the settings API helpers**

  Add the shared helper with URL encoding, credentials, JSON error extraction, and the separate `/settings` versus `/admin/settings` read paths.

- [ ] **Step 3: Expand the settings page**

  Load public and admin settings independently, prefill effective fallback values, add payment inputs, add maintenance toggle/message controls, and preserve existing loading/success/error modal behavior. Save each section with disabled controls and visible “Menyimpan...” state.

- [ ] **Step 4: Restrict Settings navigation/page to staff**

  Use the existing `me.role` state to hide the Settings menu item for mentors and render an access-denied state if a non-admin reaches the route directly.

- [ ] **Step 5: Run frontend type/lint verification**

  From `TCMudahFE`:

  ```powershell
  npx tsc --noEmit
  npm run lint
  ```

  Expected: no TypeScript or Biome errors.

- [ ] **Step 6: Commit the CMS settings UI**

  ```powershell
  git add lib/settings.ts src/app/cms/settings/page.tsx src/app/cms/components/CMSLayoutClient.tsx
  git commit -m "feat: add payment and maintenance settings UI"
  ```

### Task 4: Add the global participant maintenance gate

**Files:**
- Create: `TCMudahFE/src/components/providers/MaintenanceGate.tsx`
- Create: `TCMudahFE/src/components/providers/MaintenanceGate.test.ts`
- Create: `TCMudahFE/src/components/MaintenanceScreen.tsx`
- Modify: `TCMudahFE/src/app/layout.tsx`

**Interfaces:**
- `MaintenanceGate({ children }: { children: React.ReactNode })` wraps the application and owns polling/focus refresh.
- `MaintenanceScreen({ message }: { message: string })` renders the configured message without exposing CMS controls.
- The gate bypasses `/cms`, `/login`, and `/register`; failed state requests render children normally.

- [ ] **Step 1: Write the path/state behavior checks**

  Add pure exported helpers `isMaintenanceBypassPath(pathname: string): boolean` and `shouldShowMaintenance(pathname: string, enabled: boolean, requestFailed: boolean): boolean` in the provider, with `MaintenanceGate.test.ts` covering CMS/auth bypass, participant enabled, and request-failure fallback.

- [ ] **Step 2: Run the checks and verify RED**

  Run the project’s available TypeScript check against the fixture; expected failure because the provider/helpers do not exist.

- [ ] **Step 3: Implement the gate and screen**

  Fetch `maintenance_mode` and `maintenance_message` with `cache: "no-store"`, refresh on pathname/focus and a bounded interval, skip bypass routes, and leave children rendered when the request fails. Use the existing dark theme and a restrained, icon-light layout.

- [ ] **Step 4: Mount the gate in the root layout**

  Keep `ErrorProvider` behavior intact and wrap its children with `MaintenanceGate` so CMS/auth access is preserved.

- [ ] **Step 5: Run frontend type/lint verification**

  ```powershell
  npx tsc --noEmit
  npm run lint
  ```

  Expected: no TypeScript or Biome errors.

- [ ] **Step 6: Commit the maintenance gate**

  ```powershell
  git add src/components/providers/MaintenanceGate.tsx src/components/MaintenanceScreen.tsx src/app/layout.tsx
  git commit -m "feat: add participant maintenance gate"
  ```

### Task 5: Document the migration and perform full verification

**Files:**
- Modify: `tcmudahbe/README.md` to document the two-phase env migration and new CMS fields
- Modify: `tcmudahbe/.env.example` to mark checkout env variables as transitional during the first deploy
- Modify: `TCMudahFE/README.md` only if the frontend route behavior needs local setup notes

- [ ] **Step 1: Add migration runbook text**

  Document: deploy DB-first fallback, open `/cms/settings`, save all four payment values, verify `/checkout/info` and maintenance on/off, then remove `BANK_NAME`, `BANK_ACCOUNT`, `BANK_HOLDER`, and `GROUP_LINK` from the deployment environment and config in a follow-up cleanup deploy.

- [ ] **Step 2: Run the complete backend suite**

  From `tcmudahbe`:

  ```powershell
  pytest -q
  ```

  Expected: exit code 0 with no failed tests.

- [ ] **Step 3: Run the complete frontend checks/build**

  From `TCMudahFE`:

  ```powershell
  npx tsc --noEmit
  npm run lint
  npm run build
  ```

  Expected: all commands exit 0.

- [ ] **Step 4: Inspect the final diff and verify scope**

  Confirm only settings, checkout maintenance guards, CMS UI, maintenance gate, tests, and migration documentation changed; confirm no payment value is hardcoded into tracked source.

- [ ] **Step 5: Commit migration documentation**

  ```powershell
  git add README.md .env.example
  git commit -m "docs: document settings migration"
  ```

## Execution Handoff

The plan is ready for implementation. Because the work crosses two repos and
the interfaces are sequential (settings service before checkout guard, then
CMS/gate), Native execution is recommended for a single consistent integration
pass. The implementer should use `superpowers:executing-plans` and complete each
task’s failing-test, implementation, verification, and commit steps in order.
