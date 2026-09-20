# Performance Operations Runbook

Dokumen ini adalah kontrak operasional PERF-06 sampai PERF-10. Perubahan aplikasi
bergantung pada migration `202609200001_perf_01_05.sql` lalu
`202609200002_perf_06_10.sql`; jangan membalik urutannya.

## Rollout database

1. Ambil backup database dan lakukan rollout lebih dulu di staging.
2. Jadwalkan migration kedua pada periode write rendah. Migration memakai
   `lock_timeout=10s` agar gagal cepat alih-alih menahan traffic bila tabel sedang sibuk.
3. Terapkan kedua migration melalui Supabase CLI/workflow migration. Jika migration
   pertama sudah pernah diterapkan, hanya jalankan migration kedua.
4. Jalankan verifikasi berikut sebelum deploy backend:

```sql
select count(*) as duplicate_enrollments
from (
  select user_id, class_id
  from public.enrollments
  group by user_id, class_id
  having count(*) > 1
) duplicates;

select
  (select count(*) from public.orders) as orders,
  (select count(distinct order_id) from public.order_items) as normalized_orders,
  (select count(*) from public.order_items) as normalized_items;

select routine_name
from information_schema.routines
where routine_schema = 'public'
  and routine_name in (
    'admin_set_user_enrollments',
    'admin_set_package_enrollments',
    'admin_paginated_orders',
    'create_order_transactional',
    'admin_update_order_status',
    'admin_paginated_feedbacks',
    'admin_paginated_shortlinks',
    'get_public_catalog'
  )
order by routine_name;
```

`duplicate_enrollments` harus nol. `normalized_orders` boleh lebih kecil dari `orders`
hanya jika order lama memang mempunyai `items=[]`. Migration berjalan dalam satu
transaksi: bila satu statement gagal, seluruh migration kedua di-rollback.

## Deployment dan smoke test

Deploy backend sebelum frontend. Uji minimal:

- save/clear enrollment dan assign package;
- create order valid, penolakan item tersembunyi, list order, update status;
- pagination/search order, feedback, shortlink, dan users;
- `GET /catalog`, request ulang dengan `If-None-Match`, serta response `304`;
- CMS overview, terutama revenue split dan top classes.

Jangan hapus kolom JSON `orders.items`: kolom itu dipertahankan sebagai snapshot
kompatibilitas response. `order_items` adalah bentuk relasional untuk query list dan
analytics; order baru menulis keduanya dalam transaksi yang sama.

## Observability

Setiap HTTP response mengekspos:

- `X-Request-ID` untuk korelasi;
- `X-DB-Queries` untuk jumlah call PostgREST/RPC;
- `X-Instance-Cold` (`1` hanya pada request pertama process);
- `Server-Timing` untuk total durasi DB dan aplikasi.

Log `http_request`, `slow_db_call`, dan `db_call_failed` berbentuk JSON dan sengaja
tidak memuat body, JWT, key, password, atau URL bukti pembayaran. Atur
`SLOW_QUERY_MS` (default 300 ms) sesuai baseline. Endpoint admin
`GET /admin/observability/latency` menyimpan maksimal 1.000 sample per route dan
hanya menggambarkan process aktif; agregasi lintas instance dan retensi historis harus
dilakukan oleh log/metrics platform deployment.

Baseline wajib membandingkan cold request, 10 warm sequential request, dan 10–20
request concurrent untuk enrollment bootstrap, order list, overview, serta catalog.
Pantau p50/p95/p99, query count, DB duration, response bytes, error rate, dan region.

## Cache catalog

`GET /catalog` memakai `max-age=60`, `s-maxage=300`,
`stale-while-revalidate=600`, ETag, dan `Surrogate-Key: public-catalog`. Setelah admin
mengubah batch, mentor, curriculum, class, atau package, purge surrogate key pada CDN
bila provider mendukungnya. Tanpa purge, perubahan akan konsisten paling lambat sesuai
TTL edge; ETag mencegah transfer body ketika representasi tidak berubah.

## Rollback

Rollback aplikasi dilakukan dengan mengembalikan backend/frontend ke release lama;
tabel `order_items`, index, dan RPC baru aman dibiarkan karena additive. Jangan drop
`order_items` setelah order baru dibuat: data snapshot relasionalnya sudah menjadi
bagian dari transaksi order. Database rollback destruktif hanya dilakukan dari backup
setelah menghentikan write dan memverifikasi release target.
