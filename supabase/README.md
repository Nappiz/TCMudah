# Supabase migrations

Migration di folder ini adalah bagian dari kontrak runtime backend. Terapkan migration
sebelum men-deploy versi backend/frontend yang bergantung kepadanya.

Untuk optimasi PERF-01 sampai PERF-05, apply:

```text
supabase/migrations/202609200001_perf_01_05.sql
```

Urutan rollout yang aman:

1. Terapkan migration ke environment tujuan melalui workflow migration Supabase proyek.
2. Pastikan lima function berikut tersedia untuk role `service_role`:
   `admin_paginated_users`, `admin_enrollment_candidates`,
   `admin_enrollment_bootstrap`, `admin_notification_summary`, dan
   `admin_dashboard_overview`.
3. Deploy backend.
4. Deploy frontend.
5. Jalankan smoke test untuk Users, Enrollments, notification badge, dan CMS Overview.

Jangan deploy aplikasi lebih dulu: endpoint baru sengaja gagal dengan jelas apabila
kontrak RPC belum tersedia, alih-alih diam-diam kembali ke query lama yang lambat.
