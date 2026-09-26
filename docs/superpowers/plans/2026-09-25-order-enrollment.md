# Order Enrollment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Approving a new participant order grants the purchased classes automatically while preserving existing data and catalog history.

**Architecture:** A migration marks existing orders for manual fulfillment and adds an immutable grant ledger. New orders snapshot package members at checkout. One database RPC validates a pending order, records grants, activates enrollments, and updates status atomically. Catalog deletion archives rows, and the CMS exposes the purchase snapshot before approval.

**Tech Stack:** PostgreSQL/Supabase SQL, FastAPI/Python, Next.js/React/TypeScript.

**Spec:** `docs/superpowers/specs/2026-09-25-order-enrollment.md`

## Global Constraints

- Preserve unrelated dirty changes in both repositories.
- Existing orders and enrollments retain their current access and fulfillment behavior.
- Approved-order expiration does not revoke access.
- Apply the migration before deploying the backend and frontend.

## Review Focus

- Repeated approval must not duplicate a grant or reactivate access manually removed after approval.
- A missing class or malformed package snapshot must roll back the approval.
- Editing a package after checkout must not change the classes granted by its pending order.
- Archiving a class must stop affected packages from being sold.
- Old pending orders must remain manual while new orders use automatic fulfillment.

---

### Task 1: Database approval and checkout snapshot

**Files:** Create `supabase/migrations/202609250004_order_enrollment.sql` and `tests/sql/test_order_enrollment.sql`.

**Interfaces:** `admin_update_order_status(uuid,text)` keeps its signature; `orders.fulfillment_mode` is `legacy_manual` or `automatic`; `order_enrollment_grants` records one grant per order item and class.

- [ ] Write SQL integration cases for new class and package approval, legacy approval, retry, rollback, and expiration. Run them against the existing schema and observe failure.
- [ ] Add the grant table and fulfillment mode, replace checkout snapshot creation and approval RPC, and expose fulfillment mode in admin order pagination. Run the SQL cases and observe success.
- [ ] Add a read-only reconciliation query for legacy orders and enrollment mismatches.

### Task 2: Catalog archival

**Files:** Modify `app/crud/crud_class.py`, `app/crud/crud_package.py`; add migration changes and CRUD regression tests.

**Interfaces:** Existing DELETE API routes archive catalog rows; admin lists exclude archived rows; historical by-ID reads remain available.

- [ ] Write tests showing deletion archives rows and removes archived rows from admin lists. Run and observe failure.
- [ ] Add `archived_at`, an atomic class archive RPC that archives dependent packages, and update CRUD reads/writes. Run tests and observe success.

### Task 3: CMS order review

**Files:** Modify `TCMudahFE/lib/orders.ts`, `TCMudahFE/src/app/cms/orders/components/OrdersPage.tsx`, and `OrdersTable.tsx`; create `OrderDetailModal.tsx`.

**Interfaces:** Order rows include `fulfillment_mode` and nested package class title, offer, price, and meeting count snapshots.

- [ ] Add focused presentation coverage where the frontend test runner is available, then implement a details modal and route approval through it.
- [ ] Explain manual fulfillment on legacy pending orders and automatic access on new pending orders. Verify TypeScript/build and inspect the screen.

### Task 4: Release verification

**Files:** Modify `supabase/README.md` and any affected API tests.

- [ ] Run the SQL integration cases, complete backend pytest suite, and frontend typecheck/build.
- [ ] Review the diff for legacy access preservation, order transition rules, and unrelated local changes.
