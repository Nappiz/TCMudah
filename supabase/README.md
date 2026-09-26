# Supabase migrations

Migration di folder ini adalah bagian dari kontrak runtime backend. Terapkan migration
sebelum men-deploy versi backend/frontend yang bergantung kepadanya.

Untuk optimasi PERF-01 sampai PERF-15, apply migration berikut **sesuai urutan**:

```text
supabase/migrations/202609200001_perf_01_05.sql
supabase/migrations/202609200002_perf_06_10.sql
supabase/migrations/202609200003_perf_11_15.sql
supabase/migrations/202609250001_class_offers.sql
supabase/migrations/202609250002_atomic_class_offer_updates.sql
supabase/migrations/202609250003_fix_order_status_enum_cast.sql
supabase/migrations/202609250004_order_enrollment.sql
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
4. Terapkan migration PERF-11–15. Pastikan bucket `PAYMENTS_BUCKET` bersifat private;
   RPC upload intent akan menolak konfigurasi bucket public.
5. Jalankan query verifikasi dari
   [`PERFORMANCE_OPERATIONS.md`](../PERFORMANCE_OPERATIONS.md) dan pastikan tidak ada
   duplicate enrollment atau order yang gagal dibackfill.
6. Terapkan migrasi class offers dan order enrollment sesuai urutan di atas. Semua order
   yang sudah ada mendapat `fulfillment_mode = legacy_manual`; order baru dibuat dalam
   mode `automatic`. Migrasi tidak mengubah enrollment yang sudah ada.
7. Jalankan [`order_enrollment_audit.sql`](order_enrollment_audit.sql) untuk memeriksa
   pending order lama dan histori paket yang belum mempunyai snapshot. Selesaikan pending
   order lama melalui alur enrollment manual.
8. Deploy backend dan frontend dari release yang sama karena kontrak upload dan approval
   order berubah. Setelah migrasi aktif, DELETE kelas/paket mengarsipkan data.
9. Jalankan smoke test untuk Users, Enrollments, Orders, Feedback, Shortlinks,
   notification badge, CMS Overview, dan public catalog.

Jangan deploy aplikasi lebih dulu: endpoint baru sengaja gagal dengan jelas apabila
kontrak RPC belum tersedia, alih-alih diam-diam kembali ke query lama yang lambat.
