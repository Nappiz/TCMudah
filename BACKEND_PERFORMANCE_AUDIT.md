# Audit Ekstrem Performa Backend TC Mudah

Tanggal audit: 20 September 2026  
Scope: `tcmudahbe` dan pola pemanggilan API di `TCMudahFE`  
Jenis audit: static code audit; belum memakai production trace, query plan, atau schema/index aktual dari Supabase

## Status implementasi PERF-01 sampai PERF-10

Status per 20 September 2026: **selesai di source code dan migration**. Migration
[`202609200001_perf_01_05.sql`](./supabase/migrations/202609200001_perf_01_05.sql) dan
[`202609200002_perf_06_10.sql`](./supabase/migrations/202609200002_perf_06_10.sql)
harus diterapkan berurutan ke database Supabase sebelum backend/frontend baru dipasang.
Bagian-bagian audit setelah tabel ini tetap dipertahankan sebagai catatan kondisi awal
dan alasan desain.

| ID | Status | Implementasi akhir |
|---|---|---|
| PERF-01 | Selesai | Initial load enrollment memakai satu `GET /admin/enrollments/bootstrap`; pergantian user hanya meminta daftar `class_id` aktif. GET generik tidak lagi mengirim `Content-Type`, sehingga tidak memicu preflight hanya karena header tersebut. |
| PERF-02 | Selesai | `GET /admin/users` memanggil satu RPC `admin_paginated_users`, termasuk urutan role dan total di response yang sama. Batas halaman maksimum 100 diterapkan di API. |
| PERF-03 | Selesai | Kandidat enrollment dicari dan dipaginasi dengan cursor melalui `admin_enrollment_candidates`; eligibility memakai SQL `EXISTS`, tanpa mengunduh semua approved order. Jalur frontend lama `limit=10000` sudah dihapus. |
| PERF-04 | Selesai | Summary notification memakai satu RPC agregat, satu provider bersama, polling 60 detik, dan polling berhenti saat tab tidak terlihat. |
| PERF-05 | Selesai | Overview memakai satu `GET /admin/dashboard/overview`; statistik, filter periode, time series, revenue split, dan top class dihitung di PostgreSQL. Response list dibatasi untuk pending/recent order. |
| PERF-06 | Selesai | Middleware ASGI mengirim request ID, cold-instance marker, query count, dan `Server-Timing`; wrapper Supabase mencatat durasi/row setiap call; log JSON aman dan endpoint admin menyediakan p50/p95/p99 per route untuk instance aktif. |
| PERF-07 | Selesai | Seluruh `select("*")` dihapus, projection dibuat per use case, dan list yang tumbuh (users, orders, feedbacks, shortlinks) dipaginasi dengan batas maksimum 100. History order user juga dibatasi dengan limit/offset. |
| PERF-08 | Selesai | Save enrollment user dan package masing-masing memakai satu RPC transaksional. Input divalidasi di API dan database; duplikat legacy dikonsolidasikan sebelum unique index `(user_id, class_id)` dipasang. |
| PERF-09 | Selesai | Order list/count/title memakai satu RPC; create dan status update memakai RPC atomik; item tak terlihat ditolak; title/price disnapshot; `order_items` menjadi sumber analytics tanpa ekspansi JSON saat request. |
| PERF-10 | Selesai | Public catalog memakai satu `GET /catalog` → satu RPC, membaca active batch sekali, projection eksplisit, ETag, conditional 304, serta cache browser/CDN dengan stale-while-revalidate dan surrogate key. Semua consumer katalog utama memakai endpoint gabungan. |

Coverage regresi ditambahkan pada CRUD, middleware, dan router baru. Prosedur rollout,
observability, baseline, serta rollback dijelaskan di
[`PERFORMANCE_OPERATIONS.md`](./PERFORMANCE_OPERATIONS.md).
Verifikasi lokal terakhir: 127 test backend lulus, seluruh modul Python berhasil
dikompilasi, TypeScript type-check dan Biome check lulus, serta Next.js production
build selesai tanpa error.

## Ringkasan eksekutif

Latensi sekitar 3 detik sangat masuk akal dari implementasi saat ini, tetapi penyebab utamanya bukan sekadar Supabase Free atau beda domain. Pada `/cms/enrollments`, frontend menjalankan empat request data utama secara **berurutan**, lalu menjalankan request enrollment setelah user pertama terpilih. Di saat yang sama, layout CMS juga mengambil `/me` dan notification summary.

Lima endpoint yang disebut dalam konteks awal (`classes`, `packages`, `orders`, `enrollments`, dan `summary`) sebenarnya belum mencakup seluruh request. Implementasi saat ini juga mengambil `users` dan `/me`. Satu kali membuka halaman dapat menghasilkan:

- sekitar **7 HTTP GET dari browser**;
- hingga **5 CORS preflight tambahan** pada cache preflight yang dingin;
- sekitar **14–18 round-trip FastAPI → Supabase**;
- payload seluruh user dan order sampai `limit=10000`, padahal halaman hanya membutuhkan sebagian kecil kolom dan user yang memiliki order approved.

Dengan kata lain, endpoint count di browser hanya permukaan. Beberapa endpoint melakukan 3–6 query Supabase secara internal.

Target arsitektur yang disarankan:

1. Satu endpoint khusus `GET /admin/enrollments/bootstrap` untuk data awal halaman.
2. Idealnya endpoint itu memanggil **satu PostgreSQL RPC/function** yang mengembalikan JSON berisi peserta eligible, kelas, paket, dan enrollment user awal.
3. Notification summary tetap endpoint terpisah karena freshness-nya berbeda, tetapi tiga count digabung menjadi satu query agregat.
4. User/order tidak lagi diunduh sampai 10.000 row untuk difilter di browser.
5. Tambahkan observability sebelum dan sesudah perubahan agar cold start, waktu FastAPI, dan waktu Supabase dapat dibedakan.

Jika dilakukan dengan benar, initial load enrollment dapat turun dari sekitar 7 browser request dan 14–18 query Supabase menjadi sekitar 3 browser request (`/me`, summary, bootstrap) dan 2 query Supabase (1 summary + 1 bootstrap). Pergantian user selanjutnya cukup satu query kecil untuk `active_class_ids`.

## Prioritas temuan

| ID | Prioritas | Temuan | Dampak | Rekomendasi ringkas |
|---|---:|---|---|---|
| PERF-01 | P0 | Waterfall serial di halaman enrollment | Sangat tinggi | Ganti dengan endpoint bootstrap; jangan serial fetch empat resource |
| PERF-02 | P0 | `/admin/users` melakukan sampai 6 query | Sangat tinggi | Satu query/RPC dengan role rank dan count dalam response yang sama |
| PERF-03 | P0 | Seluruh approved orders diambil hanya untuk memperoleh `user_id` | Sangat tinggi | Endpoint/query `enrollment-candidates` dengan `EXISTS` dan projection user |
| PERF-04 | P0 | Notification summary melakukan 3 count serial setiap 30 detik | Tinggi dan berulang | Satu aggregate query/RPC; jangan mengambil seluruh `id` |
| PERF-05 | P0 | CMS overview mengunduh semua dataset dan menghitung agregat di browser | Sangat tinggi saat data tumbuh | Endpoint `/admin/dashboard/overview` berbasis agregasi SQL |
| PERF-06 | P0 | Belum ada latency instrumentation | Menghambat diagnosis | `Server-Timing`, request ID, query timing, p50/p95/p99 |
| PERF-07 | P1 | Banyak `select("*")` dan list tanpa pagination | Tinggi saat data tumbuh | Projection per use case dan pagination/cursor |
| PERF-08 | P1 | Write enrollment 4–5 round-trip tanpa transaksi | Tinggi + risiko inkonsisten | Satu transactional RPC dengan upsert/delete/returning |
| PERF-09 | P1 | Order list membutuhkan 2–4 query per request | Tinggi | Count+data satu call; simpan title snapshot atau normalisasi item |
| PERF-10 | P1 | Public catalog tersebar di 4 endpoint dan active batch dicari berulang | Sedang–tinggi | Endpoint/RPC catalog + cache HTTP |
| PERF-11 | P1 | GET admin memicu preflight karena `Content-Type: application/json` | Sedang | Jangan set Content-Type pada GET; pertimbangkan same-origin API path |
| PERF-12 | P1 | Kandidat indeks dan constraint tidak terversi di repo | Tinggi saat data tumbuh | Tambahkan migration resmi dan validasi dengan `EXPLAIN` |
| PERF-13 | P2 | Seluruh Supabase call bersifat synchronous | Sedang pada concurrency | Migrasi penuh ke async client; jangan membuat `async def` dengan client sync |
| PERF-14 | P2 | Upload bukti pembayaran melewati memory FastAPI | Sedang | Signed direct upload dengan validasi ukuran/type |
| PERF-15 | P2 | Feedback, material, setting, batch, shortlink memakai read-then-write/multi-query | Sedang | Join/RPC/upsert/atomic update |

## Bedah khusus `/cms/enrollments`

### Request graph aktual

Layout CMS menjalankan:

1. `GET /me` dari `CMSLayoutClient`;
2. `GET /admin/notifications/summary`, lalu mengulanginya setiap 30 detik.

Hook enrollment kemudian menjalankan secara serial:

3. `GET /admin/users?page=1&limit=10000`;
4. `GET /admin/classes`;
5. `GET /admin/packages`;
6. `GET /admin/orders?status=approved&limit=10000`;
7. setelah user pertama dipilih, `GET /admin/enrollments?user_id=...`.

Evidence utama:

- Frontend sengaja melakukan fetch berurutan di [`useEnrollments.ts`](../TCMudahFE/src/hooks/useEnrollments.ts#L47-L56).
- Semua approved order diambil dari [`admin.ts`](../TCMudahFE/lib/admin.ts#L95-L100).
- Summary berjalan setiap 30 detik di [`useNotifications.ts`](../TCMudahFE/src/hooks/useNotifications.ts#L49-L54).
- `/me` dijalankan oleh layout CMS di [`CMSLayoutClient.tsx`](../TCMudahFE/src/app/cms/components/CMSLayoutClient.tsx#L68-L86).

Komentar frontend menyebut serialisasi dilakukan untuk menghindari `[WinError 10035]`. Ini adalah workaround terhadap masalah concurrency/socket yang belum didiagnosis, bukan solusi performa. Efek langsungnya adalah latency empat request dijumlahkan, bukan hanya mengambil nilai request paling lambat.

Secara sederhana:

```text
sekarang: T_users + T_classes + T_packages + T_orders + T_enrollments
paralel:  max(T_users, T_classes, T_packages, T_orders) + T_enrollments
RPC:      T_bootstrap
```

### Query Supabase di balik tiap endpoint

| Browser endpoint | Query Supabase | Penjelasan |
|---|---:|---|
| `/me` | 0 | JWT dibaca lokal; ini sudah efisien |
| `/admin/notifications/summary` | 3 | Count orders, users, feedbacks dilakukan serial |
| `/admin/users?limit=10000` | sampai 6 | 3 count per kelompok role + sampai 3 fetch per kelompok role |
| `/admin/classes` | 1–2 | Cari active batch jika cache miss, lalu ambil classes |
| `/admin/packages` | 1–2 | Cari active batch jika cache miss, lalu ambil packages |
| `/admin/orders?...` | 2–4 | Count + data + lookup title class + lookup title package |
| `/admin/enrollments?...` | 1 | Ambil seluruh row enrollment user |
| **Total** | **sekitar 14–18** | Bergantung cache active batch dan jenis item pada order |

Hitungan ini belum memasukkan CORS preflight browser, serialization/validation response, dan kemungkinan cold start Vercel.

### Pemborosan data terbesar

Halaman enrollment hanya membutuhkan:

- user: `id`, `full_name`, `email` milik peserta yang memiliki order approved;
- class: `id`, `title`;
- package: `id`, `title`, `class_ids`;
- enrollment: pada dasarnya cukup `class_id` aktif untuk user yang dipilih.

Namun implementasi sekarang mengambil:

- seluruh kelompok user sampai 10.000 row;
- seluruh approved order beserta JSON items, proof URL, note, nested user, count, dan title enrichment;
- `select("*")` untuk classes, packages, dan enrollments.

Frontend kemudian membangun `Set(order.user_id)` dan memfilter user di browser. Ini memindahkan pekerjaan yang seharusnya sangat murah bagi PostgreSQL ke network dan browser.

### Desain endpoint yang direkomendasikan

Tambahkan endpoint use-case-specific:

```http
GET /admin/enrollments/bootstrap?user_id=<optional>&q=<optional>&limit=50&cursor=<optional>
```

Response minimal:

```json
{
  "participants": [
    { "id": "...", "full_name": "...", "email": "..." }
  ],
  "next_cursor": null,
  "classes": [
    { "id": "...", "title": "..." }
  ],
  "packages": [
    { "id": "...", "title": "...", "class_ids": ["..."] }
  ],
  "selected_user_id": "...",
  "active_class_ids": ["..."]
}
```

Query peserta eligible seharusnya berbentuk `EXISTS`, bukan mengambil semua order:

```sql
select u.id, u.full_name, u.email
from public.users u
where u.role = 'peserta'
  and exists (
    select 1
    from public.orders o
    where o.user_id = u.id
      and o.status = 'approved'
  )
order by u.full_name, u.id
limit :limit;
```

Ada dua level implementasi:

1. **Quick win:** satu browser endpoint yang menjalankan beberapa query kecil dari FastAPI. Ini menghilangkan waterfall browser, cold invocation berulang, dan sebagian preflight, tetapi masih memiliki beberapa round-trip ke Supabase.
2. **Recommended:** satu PostgreSQL function/RPC yang memakai `jsonb_build_object` dan subquery/CTE untuk mengembalikan seluruh payload. FastAPI cukup melakukan satu `.rpc(...).execute()`.

Jangan gabungkan notification summary ke bootstrap enrollment. Summary bersifat global CMS dan di-refresh periodik, sedangkan bootstrap enrollment hanya perlu saat membuka halaman atau refresh manual. Menggabungkan keduanya membuat cache dan lifecycle data menjadi buruk.

### Apakah perlu mapping table?

**Bukan prioritas pertama untuk mengatasi latency halaman ini.** Mapping table memperbaiki relasi dan integritas data, tetapi tidak otomatis mengurangi jumlah HTTP request atau query.

Untuk `packages.class_ids`, array masih cukup efisien jika:

- jumlah class per package kecil;
- hanya dibaca sebagai satu unit;
- jarang ada query “package apa saja yang memiliki class X?”;
- validasi foreign key tidak terlalu dibutuhkan.

Normalisasi layak dilakukan jika kebutuhan relasional tumbuh:

```sql
create table public.package_classes (
  package_id uuid not null references public.packages(id) on delete cascade,
  class_id uuid not null references public.classes(id) on delete cascade,
  position integer not null default 0,
  primary key (package_id, class_id)
);
```

Manfaatnya adalah foreign key, ordering, join, dan pencarian membership yang lebih baik. Untuk performa initial page saat ini, endpoint agregat + projection akan memberi dampak jauh lebih besar daripada migrasi array ke mapping table.

## Temuan detail lintas backend

### PERF-02 — `/admin/users` melakukan sampai 6 query

`get_paginated_users()` membagi role menjadi tiga grup (`superadmin`, `admin`, dan `mentor/peserta`). Masing-masing grup dihitung terpisah, lalu datanya juga diambil terpisah. Pada request tanpa filter role, ini berarti sampai enam request Supabase yang semuanya synchronous dan serial.

Evidence: [`crud_user.py`](app/crud/crud_user.py#L36-L85).

Solusi:

- buat view/RPC yang menambahkan `role_rank` menggunakan `CASE`;
- lakukan filter, sorting, range, dan count dalam satu response;
- untuk layar enrollment, jangan reuse endpoint user generik—gunakan query peserta eligible khusus;
- jadikan exact total opsional. Untuk tabel besar, exact count pada setiap page bisa lebih mahal daripada data page-nya.

Catatan correctness: endpoint user membuang `created_at` saat membentuk response, sedangkan CMS overview mengharapkannya untuk menghitung `newUsers30d`. Hasil metrik itu saat ini berpotensi selalu nol. Endpoint overview khusus sekaligus menyelesaikan masalah ini.

### PERF-03 — Approved order dipakai sebagai pengganti query eligibility

`fetchApprovedOrders()` meminta sampai 10.000 order. Backend tetap menjalankan count, join user, title enrichment, dan membentuk seluruh response order, sementara enrollment page hanya memakai `user_id`.

Evidence:

- [`admin.ts`](../TCMudahFE/lib/admin.ts#L95-L97)
- [`orders.py`](app/routers/orders.py#L75-L128)
- [`crud_order.py`](app/crud/crud_order.py#L56-L90)

Solusi terbaik adalah query `users WHERE EXISTS approved order`. Alternatif minimum adalah endpoint `GET /admin/orders/approved-user-ids` dengan `select user_id distinct`, tetapi response peserta langsung lebih baik karena menghindari fetch semua user.

`limit=10000` juga bukan jaminan semua data akan dikembalikan; batas maximum rows di layer API Supabase dapat lebih rendah. Ini membuat peserta eligible berpotensi hilang diam-diam selain memboroskan payload.

### PERF-04 — Notification summary mahal dan terus berulang

Endpoint summary melakukan tiga query count satu per satu. Query menggunakan `select("id", count="exact")` tanpa mode head dan tanpa limit, sehingga juga berpotensi mengirim body berisi seluruh ID yang cocok, bukan hanya count. Ini diulang setiap 30 detik selama layout CMS terpasang, termasuk ketika tab tidak aktif.

Evidence:

- [`crud_notifications.py`](app/crud/crud_notifications.py#L3-L25)
- [`useNotifications.ts`](../TCMudahFE/src/hooks/useNotifications.ts#L14-L54)

Solusi:

- satu SQL aggregate dengan `COUNT(*) FILTER (WHERE ...)` atau scalar subqueries;
- panggil melalui satu RPC;
- response hanya tiga integer;
- cache hasil 15–30 detik bila acceptable;
- hentikan polling ketika `document.visibilityState !== "visible"` dan refresh saat focus;
- pertimbangkan interval 60–120 detik jika badge tidak memerlukan near-real-time.

Contoh bentuk agregasi:

```sql
select
  (select count(*) from orders where status = 'pending') as new_orders,
  (select count(*) from users where created_at > :last_seen_users) as new_users,
  (select count(*) from feedbacks where created_at > :last_seen_feedbacks) as new_feedbacks;
```

### PERF-05 — CMS overview menghitung analytics di browser

CMS overview mengambil `/me`, lalu enam endpoint. User dan order diminta sampai 10.000 row dan seluruh statistik, revenue, serta chart dihitung dengan JavaScript di browser.

Evidence: [`useCMSOverview.ts`](../TCMudahFE/src/hooks/useCMSOverview.ts#L227-L260).

Ini akan melambat secara linear mengikuti jumlah order dan user, meningkatkan transfer, dan membuat hasil salah jika data melewati limit API.

Buat `GET /admin/dashboard/overview?days=30` yang mengembalikan:

- counts user per role;
- new users 30 hari;
- count content/visible content;
- order count per status;
- approved revenue, AOV, approval rate;
- active participants;
- time series order/revenue yang sudah di-group per hari;
- hanya beberapa recent order untuk activity feed.

Idealnya satu RPC dengan aggregate PostgreSQL. Jangan mengirim raw 10.000 row untuk menghitung belasan angka.

### PERF-07 — `select("*")` dan endpoint tanpa batas

`select("*")` digunakan pada classes, packages, orders, enrollments, materials, mentors, testimonials, shortlinks, batches, settings, dan lookup user. Banyak list endpoint tidak memiliki pagination.

Masalahnya bukan hanya ukuran payload. Kolom JSON/array seperti `items`, `description`, `mentor_ids`, `curriculum_ids`, `class_ids`, `achievements`, dan URL panjang ikut melewati PostgREST, Python, Pydantic, JSON encoder, network, lalu browser walau tidak dipakai.

Aturan yang disarankan:

- buat projection per use case;
- list UI hanya mengambil kolom untuk row/table/card;
- detail endpoint mengambil body besar;
- pagination wajib untuk `users`, `orders`, `feedbacks`, `shortlinks`, dan list lain yang dapat terus tumbuh;
- cursor/keyset pagination lebih stabil daripada offset untuk order besar;
- content kecil dan bounded seperti mentor/curriculum dapat tetap satu page, tetapi diberi cache.

### PERF-08 — Write enrollment banyak round-trip dan tidak atomik

`POST /admin/enrollments/set` melakukan:

1. select enrollment lama;
2. delete yang dihapus;
3. insert yang baru;
4. update semua requested class menjadi active;
5. select hasil akhir.

`set-by-package` memiliki pola serupa. Selain lambat, kegagalan di tengah proses dapat meninggalkan state parsial karena operasi tidak dibungkus satu transaksi.

Evidence: [`enrollments.py`](app/routers/enrollments.py#L10-L59).

Solusi: satu RPC transactional yang:

- memvalidasi user dan class;
- upsert `(user_id, class_id)` yang diinginkan;
- menghapus/menonaktifkan row yang tidak diinginkan sesuai business rule;
- mengembalikan `active_class_ids` dengan `RETURNING`/select akhir di dalam transaksi.

Pastikan ada unique constraint `(user_id, class_id)`.

### PERF-09 — Order list dan mutation melakukan query tambahan

List order melakukan count terpisah, fetch data, kemudian lookup title class dan package. Update status melakukan update lalu select ulang.

Perbaikan bertahap:

1. ambil data dan count dalam satu PostgREST response;
2. projection eksplisit;
3. simpan `item_title` sebagai snapshot di JSON `orders.items` ketika order dibuat. Harga sudah di-snapshot, title seharusnya diperlakukan serupa untuk histori;
4. jika analytics per item akan menjadi penting, normalisasi menjadi `order_items`;
5. gunakan update dengan representation/returning agar update status tidak memerlukan select kedua;
6. untuk create order, satukan validasi harga dan insert dalam RPC agar atomik.

Catatan correctness: query harga mengambil kolom `visible`, tetapi kode tidak menolak item yang `visible=false`. RPC validasi adalah tempat yang tepat untuk memperbaikinya.

### PERF-10 — Public catalog terfragmentasi

`fetchCatalog()` memanggil mentors, curriculum, classes, dan packages secara paralel. Classes dan packages masing-masing mencari active batch. Cache active batch saat ini hanya in-memory per process selama 60 detik.

Evidence:

- [`api.ts`](../TCMudahFE/lib/api.ts#L88-L96)
- [`crud_batch.py`](app/crud/crud_batch.py#L4-L19)
- [`crud_class.py`](app/crud/crud_class.py#L4-L26)
- [`crud_package.py`](app/crud/crud_package.py#L4-L26)

Masalah cache sekarang:

- tidak shared antar-instance serverless;
- cold instance selalu miss;
- request classes/packages yang paralel dapat sama-sama miss;
- hasil “tidak ada active batch” tidak pernah benar-benar di-cache karena fast path mensyaratkan `id is not None`.

Rekomendasi:

- `GET /catalog` atau RPC `get_public_catalog()`;
- active batch dibaca sekali di dalam query/function;
- tambahkan `Cache-Control: public, s-maxage=300, stale-while-revalidate=...` untuk konten publik;
- invalidasi/revalidate setelah admin mengubah catalog;
- projection public harus eksplisit.

### PERF-11 — CORS preflight yang tidak perlu

Helper di `lib/admin.ts` selalu memasang `Content-Type: application/json`, termasuk untuk GET. Pada cross-origin request, `application/json` membuat request tidak lagi “simple” dan browser berpotensi mengirim OPTIONS preflight.

Evidence: [`admin.ts`](../TCMudahFE/lib/admin.ts#L33-L38).

Perbaikan cepat:

- hanya set `Content-Type` ketika ada JSON body;
- jangan set header itu untuk GET/HEAD;
- jika deployment memungkinkan, expose backend melalui same-origin path seperti `/api/...` menggunakan reverse proxy/rewrite;
- tetap ukur karena preflight dapat di-cache dan bukan satu-satunya sumber 3 detik.

Cross-domain sendiri biasanya hanya menambah DNS/TLS/preflight. Yang membuat dampaknya besar di aplikasi ini adalah jumlah request dan serial waterfall.

### PERF-13 — Synchronous I/O dan concurrency

Supabase client yang dipakai adalah synchronous dan router sebagian besar didefinisikan dengan `def`. FastAPI menjalankan sync route di thread pool, sehingga event loop tidak langsung terblokir, tetapi setiap query tetap menahan worker thread. Fan-out request bersamaan dapat menghabiskan thread/socket dan memperburuk tail latency.

Rekomendasi:

- prioritaskan pengurangan jumlah query terlebih dahulu;
- setelah itu, bila concurrency masih menjadi bottleneck, migrasikan repository dan route secara utuh ke async Supabase/HTTP client;
- jangan sekadar mengubah `def` menjadi `async def` sambil tetap memakai client sync—itu justru akan memblokir event loop;
- atur timeout, connection pool/keep-alive, dan concurrency limit secara eksplisit pada client yang dipilih;
- pin versi dependency agar karakteristik client tidak berubah tanpa disengaja.

Singleton client di [`supabase_client.py`](app/core/supabase_client.py) sudah merupakan langkah baik untuk reuse connection dalam instance yang hangat, tetapi manfaatnya terbatas pada lifecycle serverless instance tersebut.

### PERF-14 — Upload bukti pembayaran melewati backend

Endpoint upload membaca seluruh file ke memory (`file.file.read()`), kemudian FastAPI meng-upload ulang ke Supabase Storage. Ini menggandakan transfer dan membuat serverless function menanggung memory serta durasi upload.

Rekomendasi:

- backend menerbitkan signed upload URL/path yang scoped untuk user;
- browser upload langsung ke Storage;
- backend hanya menerima metadata/path saat create order;
- enforce ukuran, MIME type, extension, dan ownership;
- gunakan bucket private untuk bukti pembayaran dan signed read URL bagi admin.

Saat ini bucket diakses dengan nama hard-coded `payments`, walau setting `PAYMENTS_BUCKET` tersedia. Ini bukan bottleneck utama, tetapi perlu dirapikan saat flow upload diubah.

### PERF-15 — Multi-query lain yang dapat disederhanakan

| Flow | Kondisi sekarang | Optimasi |
|---|---|---|
| Admin feedback list | Fetch feedback lalu fetch class titles | FK join `classes(title)` dalam satu query |
| User materials | Check enrollment lalu fetch materials | RPC/security function atau RLS policy + satu query |
| Submit feedback | Check enrollment lalu upsert | Transactional RPC atau RLS |
| Settings PUT | Select existence lalu update/insert | Satu upsert |
| Batch activate | Deactivate semua lalu insert/update | Transactional RPC + unique partial constraint |
| Shortlink resolve | Select lalu update click counter sebelum response | Atomic RPC; atau non-blocking analytics |
| Shortlink create/update | Check slug lalu write | Unique constraint pada normalized slug, tangani conflict |
| Register | Check email lalu insert | Unique email constraint sebagai sumber kebenaran; tangani conflict |
| Order status update | Update lalu select | Update returning/representation |

Shortlink click saat ini memakai pola read-modify-write, sehingga concurrent click dapat hilang. Atomic `clicks = clicks + 1` di database memperbaiki correctness sekaligus mengurangi round-trip.

## Kandidat indeks dan constraint

Repo tidak menyertakan schema/migration Supabase lengkap, jadi tabel di bawah adalah **kandidat untuk diverifikasi**, bukan daftar SQL yang boleh diterapkan membabi buta. Cek indeks yang sudah ada dan gunakan `EXPLAIN (ANALYZE, BUFFERS)` pada data representatif.

| Tabel/use case | Kandidat |
|---|---|
| `orders`: list per status | `(status, created_at DESC)` |
| `orders`: access/eligible participant | `(user_id, status)` atau partial index `(user_id) WHERE status='approved'` |
| `orders`: history user | `(user_id, created_at DESC)` |
| `enrollments`: uniqueness | `UNIQUE (user_id, class_id)` |
| `enrollments`: kelas aktif user | `(user_id, active, created_at DESC)` |
| `classes`: active batch catalog | `(batch_id, visible, created_at DESC)` |
| `packages`: active batch catalog | `(batch_id, visible, created_at DESC)` |
| `class_materials` | `(class_id, visible, created_at DESC)` |
| `feedbacks`: admin class filter | `(class_id, created_at DESC)` |
| `feedbacks`: user history/upsert | `UNIQUE (user_id, class_id)` |
| `feedbacks`: notification | `(created_at)` bila belum tercakup |
| `users`: role list | `(role, created_at DESC)` |
| `users`: `%name%` search | `GIN (full_name gin_trgm_ops)` setelah `pg_trgm` |
| `shortlinks` | `UNIQUE (lower(slug))`; normalize lalu gunakan equality |
| `batches` | unique partial constraint/index untuk hanya satu `is_active=true` |

Query inventory awal:

```sql
select schemaname, tablename, indexname, indexdef
from pg_indexes
where schemaname = 'public'
order by tablename, indexname;
```

Catatan penting:

- jangan menambah semua kombinasi indeks sekaligus;
- setiap indeks memperlambat insert/update dan memakai storage;
- pilih antara `(user_id, status)` dan partial approved index berdasarkan workload nyata;
- leading-wildcard `ILIKE '%teks%'` tidak banyak dibantu B-tree biasa;
- exact count tetap dapat mahal walau filter memiliki indeks.

## Caching yang aman

### Sangat layak di-cache

- public catalog, mentor, curriculum, testimonial;
- active batch ID;
- classes/packages reference untuk halaman admin;
- notification summary selama 15–30 detik;
- app settings yang jarang berubah.

### Jangan cache publik

- orders, enrollment user, payment proof, user list, dan response authenticated lain;
- response dengan cookie/authorization tanpa key cache yang benar.

Strategi praktis:

- public GET: CDN `s-maxage` + `stale-while-revalidate`;
- frontend admin: SWR/React Query untuk deduplication dan stale cache singkat;
- simpan `/me` di context/layout agar page hook tidak fetch ulang;
- invalidate classes/packages setelah mutation;
- gunakan shared cache hanya jika benar-benar diperlukan; endpoint/RPC yang efisien harus tetap menjadi fondasi.

## Observability: wajib sebelum menebak cold start

Saat ini tidak ada middleware timing atau query timing. Tanpa ini, angka 3 detik tidak dapat dipisahkan menjadi:

- browser/preflight/TLS;
- Vercel queue/cold start/import;
- FastAPI/Pydantic;
- FastAPI → Supabase network;
- PostgreSQL execution;
- serialization dan transfer payload.

Tambahkan minimal:

1. `X-Request-ID` pada setiap response dan log;
2. total duration dengan `time.perf_counter()`;
3. `Server-Timing`, misalnya `app;dur=...`, `db;dur=...`, `serialize;dur=...`;
4. log structured: route, status, duration, query count, total db duration, rows, response bytes, deployment region;
5. histogram p50/p95/p99 per route;
6. penanda instance baru agar cold dan warm request dapat dibandingkan;
7. slow query threshold, misalnya log query di atas 250–500 ms.

Jangan log JWT, service-role key, password, payment proof URL, atau body sensitif.

### Benchmark yang disarankan

Ukur empat skenario terpisah:

1. cold request setelah idle;
2. 10 warm sequential request;
3. 10–20 concurrent request;
4. data kecil versus data produksi/seed yang representatif.

Untuk setiap endpoint catat DNS, connect, TLS, TTFB, total, response bytes, query count, dan DB duration. Jalankan dari lokasi yang sama dengan mayoritas user, lalu dari region backend. Pastikan region Vercel function sedekat mungkin dengan region Supabase.

Target awal yang lebih aman daripada menjanjikan angka absolut:

- request browser enrollment: 7 → 3;
- query Supabase initial enrollment: 14–18 → 2;
- tidak ada fetch `limit=10000` untuk initial page;
- payload enrollment tidak bertambah linear terhadap total order;
- list endpoint normal maksimal satu round-trip DB;
- mutation enrollment satu transaksi/round-trip;
- warm p95 ditetapkan setelah baseline tersedia.

## Rencana implementasi bertahap

### Fase 0 — Measurement, risiko rendah

1. Tambahkan request/query timing dan response size.
2. Rekam baseline cold/warm untuk enrollment, orders, overview, dan summary.
3. Ambil daftar index Supabase serta `EXPLAIN` query kritis.

### Fase 1 — Quick wins, dampak tinggi

1. Hapus `Content-Type` dari GET di `lib/admin.ts`.
2. Buat query peserta eligible khusus; hentikan fetch 10.000 users + orders.
3. Sederhanakan `/admin/users` dari sampai 6 query menjadi satu.
4. Gabungkan notification count menjadi satu aggregate query dan hentikan polling saat tab hidden.
5. Projection minimal untuk classes, packages, enrollment, dan order list.
6. Deduplicate `/me` di seluruh CMS.

### Fase 2 — Endpoint/RPC use-case-specific

1. Implementasikan `GET /admin/enrollments/bootstrap`.
2. Implementasikan transactional RPC untuk save enrollment.
3. Implementasikan `/admin/dashboard/overview` berbasis aggregate SQL.
4. Implementasikan `/catalog`/RPC dan cache public response.
5. Hilangkan title lookup order melalui snapshot atau relasi.

### Fase 3 — Database dan concurrency

1. Tambahkan migration resmi untuk index/constraint terverifikasi.
2. Uji `EXPLAIN ANALYZE` setelah data representatif tersedia.
3. Migrasikan ke async I/O hanya bila measurement menunjukkan thread/concurrency bottleneck.
4. Implementasikan direct signed upload untuk payment proof.
5. Pertimbangkan mapping table setelah kebutuhan relasional jelas.

## Hal yang sudah baik

- `/me` memverifikasi JWT secara lokal dan tidak query database.
- Supabase client dibuat singleton per warm process, sehingga berpotensi memakai connection reuse.
- Beberapa enrichment menggunakan `.in_(...)`, bukan query per row; jadi tidak ada N+1 klasik pada bagian tersebut.
- Insert enrollment sudah dibatch sebagai list, bukan satu insert per class.
- Active batch sudah memiliki cache, walau implementasinya belum cocok untuk serverless dan negative result.
- Public catalog fetch sudah paralel di frontend; masalah utamanya adalah fragmentasi/cold/cache, bukan waterfall pada fungsi itu.

## Risiko non-performa yang ditemukan saat audit

Poin ini bukan penyebab utama latency, tetapi sebaiknya tidak dilewatkan saat refactor:

- migration/schema tidak terversi secara lengkap di repo;
- `migrate_batches.py` bergantung pada modul SQLAlchemy/database config yang tidak konsisten dengan dependency dan `Settings` saat ini;
- flow aktivasi batch dan enrollment tidak transactional;
- counter shortlink dapat kehilangan update saat concurrent;
- order item `visible=false` tidak ditolak walau kolomnya diambil;
- payment proof tampaknya memakai public URL; data bukti pembayaran sebaiknya private;
- reuse endpoint user untuk overview membuang `created_at`, sehingga metrik new user berpotensi salah;
- JWT menyimpan role hingga token kedaluwarsa, sehingga perubahan role tidak langsung tercermin. Ini trade-off performa versus revocation/freshness.

## Kesimpulan

Optimasi terbesar bukan mengganti Supabase atau langsung mengubah semua relasi menjadi mapping table. Bottleneck yang terlihat dari kode adalah **terlalu banyak round-trip, waterfall serial, generic endpoint yang over-fetch, dan agregasi yang dilakukan di browser**.

Urutan paling bernilai adalah:

1. ukur cold/warm dan query duration;
2. buat enrollment bootstrap + query peserta eligible;
3. perbaiki users dan notification query fan-out;
4. pindahkan overview analytics ke SQL;
5. projection, pagination, cache, dan index;
6. baru evaluasi async client, mapping table, atau perubahan hosting berdasarkan hasil measurement.

Dengan urutan tersebut, aplikasi dapat memperoleh peningkatan besar tanpa memaksakan redesign database yang belum dibutuhkan.
