# Performance Operations Runbook

Dokumen ini adalah kontrak operasional PERF-06 sampai PERF-15. Perubahan aplikasi
bergantung pada migration `202609200001_perf_01_05.sql` lalu
`202609200002_perf_06_10.sql`, lalu `202609200003_perf_11_15.sql`; jangan membalik
urutannya.

## Rollout database

1. Ambil backup database dan lakukan rollout lebih dulu di staging.
2. Jadwalkan migration kedua dan ketiga pada periode write rendah. Migration memakai
   `lock_timeout=10s` agar gagal cepat alih-alih menahan traffic bila tabel sedang sibuk.
3. Terapkan migration melalui Supabase CLI/workflow migration. Jika dua migration
   pertama sudah diterapkan, hanya jalankan migration ketiga.
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

select id, public
from storage.buckets
where id = '<PAYMENTS_BUCKET>';

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
    'get_public_catalog',
    'get_authorized_materials',
    'submit_feedback',
    'admin_create_batch',
    'admin_update_batch',
    'resolve_shortlink',
    'create_payment_upload_intent'
  )
order by routine_name;
```

`duplicate_enrollments` harus nol. `normalized_orders` boleh lebih kecil dari `orders`
hanya jika order lama memang mempunyai `items=[]`. Migration berjalan dalam satu
transaksi: bila satu statement gagal, migration terkait di-rollback seluruhnya.

Migration ketiga juga berhenti tanpa perubahan parsial jika menemukan email, slug,
setting key, atau proof path duplikat. Selesaikan konflik tersebut berdasarkan data
bisnis; jangan menghapus row secara acak lalu mengulang migration.

## Verifikasi index dan query plan

Setelah migration ketiga, jalankan `ANALYZE` pada tabel yang banyak berubah dan cek
query kritis dengan data representatif:

```sql
analyze public.orders;
analyze public.enrollments;
analyze public.feedbacks;
analyze public.shortlinks;

explain (analyze, buffers)
select id from public.orders
where status = 'approved' and user_id = '<USER_UUID>'::uuid
order by created_at desc limit 20;

explain (analyze, buffers)
select id, title from public.class_materials
where class_id = '<CLASS_UUID>'::uuid and visible = true
order by created_at desc;
```

Bandingkan estimated row dengan actual row dan pastikan index yang dipilih sesuai
volume produksi. Jangan memaksa index hint atau menambah index duplikat.

## Deployment dan smoke test

Deploy migration lebih dulu, kemudian backend dan frontend dari release yang sama.
Uji minimal:

- save/clear enrollment dan assign package;
- create order valid, penolakan item tersembunyi, list order, update status;
- pagination/search order, feedback, shortlink, dan users;
- `GET /catalog`, request ulang dengan `If-None-Match`, serta response `304`;
- CMS overview, terutama revenue split dan top classes.
- direct upload bukti JPEG/PNG/WebP, penolakan file terlalu besar, create order,
  dan pembukaan bukti melalui signed read URL oleh admin;
- material peserta tanpa enrollment harus `403`; feedback dan shortlink click tidak
  menghasilkan duplicate/lost update ketika request concurrent.

Jangan hapus kolom JSON `orders.items`: kolom itu dipertahankan sebagai snapshot
kompatibilitas response. `order_items` adalah bentuk relasional untuk query list dan
analytics; order baru menulis keduanya dalam transaksi yang sama.

## Same-origin API dan concurrency

Browser selalu memanggil `/api`; Next.js meneruskannya ke `BACKEND_URL`. Jangan
menambahkan kembali `NEXT_PUBLIC_API_BASE`, karena itu mengembalikan browser ke
cross-domain CORS/preflight. `BACKEND_URL` harus server-only.

Runtime otomatis membatasi `SYNC_WORKER_LIMIT` agar tidak melebihi
`SUPABASE_MAX_CONNECTIONS`. Mulai dari nilai 20/20, lalu sesuaikan berdasarkan p95,
pool timeout, CPU, dan memory. Timeout default 15 detik dimaksudkan untuk gagal
terbatas, bukan menutupi query lambat.

## Private payment uploads

Bucket pada `PAYMENTS_BUCKET` wajib private. Upload intent berlaku 10 menit, terikat
pada user/path/MIME/size, hanya dapat dikonsumsi oleh create-order transaksional, dan
proof read admin berlaku 5 menit. Izinkan origin frontend pada konfigurasi CORS Storage.

Jadwalkan pembersihan harian untuk upload yang ditinggalkan sebelum checkout:

```text
python -m scripts.cleanup_expired_payment_uploads
```

Job hanya menghapus object dengan intent kedaluwarsa dan `consumed_at IS NULL`; object
yang sudah terhubung ke order tidak disentuh.

## Verifikasi lokal release PERF-11–15

Hasil terakhir pada 21 September 2026:

- `pytest -q`: 140 passed tanpa warning;
- `python -m compileall -q app scripts tests`: lulus;
- `python -m pip check`: tidak ada dependency rusak;
- `tsc --noEmit`: lulus;
- Biome check untuk seluruh file frontend yang diubah: lulus;
- `next build --turbopack`: lulus. Pesan dynamic-server saat prerender halaman utama
  di lingkungan lokal tanpa backend aktif adalah fallback server component yang
  diharapkan, bukan build failure.

Hasil ini tidak menggantikan smoke test staging, pemeriksaan preflight data migration,
atau `EXPLAIN (ANALYZE, BUFFERS)` pada volume data produksi.

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
