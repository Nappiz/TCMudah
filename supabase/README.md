# Supabase migrations

Migration di folder ini adalah bagian dari kontrak runtime backend. Terapkan migration
sebelum men-deploy versi backend/frontend yang bergantung kepadanya.

Untuk optimasi PERF-01 sampai PERF-10, apply kedua migration berikut **sesuai urutan**:

```text
supabase/migrations/202609200001_perf_01_05.sql
supabase/migrations/202609200002_perf_06_10.sql
```

Urutan rollout yang aman:

1. Terapkan migration ke environment tujuan melalui workflow migration Supabase proyek.
2. Pastikan function PERF-01–05 berikut tersedia untuk role `service_role`:
   `admin_paginated_users`, `admin_enrollment_candidates`,
   `admin_enrollment_bootstrap`, `admin_notification_summary`, dan
   `admin_dashboard_overview`.
3. Terapkan migration PERF-06–10. Migration ini menambah `order_items`, index pencarian,
   unique enrollment, RPC write enrollment/order, pagination feedback/shortlink, dan
   `get_public_catalog`.
4. Jalankan query verifikasi dari
   [`PERFORMANCE_OPERATIONS.md`](../PERFORMANCE_OPERATIONS.md) dan pastikan tidak ada
   duplicate enrollment atau order yang gagal dibackfill.
5. Deploy backend, lalu frontend.
6. Jalankan smoke test untuk Users, Enrollments, Orders, Feedback, Shortlinks,
   notification badge, CMS Overview, dan public catalog.

Jangan deploy aplikasi lebih dulu: endpoint baru sengaja gagal dengan jelas apabila
kontrak RPC belum tersedia, alih-alih diam-diam kembali ke query lama yang lambat.
