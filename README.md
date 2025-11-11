# TC Mudah – Learning Platform & CMS

TC Mudah adalah platform pembelajaran dengan sistem kelas berbayar, manajemen mentor, dan dashboard admin lengkap untuk mengelola bisnis kursus/bootcamp secara manual namun terstruktur.

Aplikasi ini dirancang agar:

- Nyaman dipakai untuk operasional bisnis sehari-hari.
- Cukup rapi dan terstruktur untuk dijadikan portofolio profesional (Next.js + FastAPI).

---

## Fitur Utama

### 1. Landing Page

Landing page publik sebagai wajah utama bisnis, berisi:

- Deskripsi singkat program dan value proposition.
- Daftar kelas yang tersedia.
- Testimoni peserta.
- Profil mentor dan kurikulum yang ditawarkan.
- CTA menuju:
  - Halaman daftar akun / login.
  - Halaman daftar kelas (`/daftar-kelas`).

---

### 2. Autentikasi & Otorisasi

- **Register** – peserta baru dapat membuat akun.
- **Login** – autentikasi pengguna menggunakan kredensial yang terdaftar.
- **Logout** – menghapus sesi pengguna.
- Role-based access yang terintegrasi dengan seluruh aplikasi:

  - `peserta`
  - `mentor`
  - `admin`
  - `superadmin`

Role menentukan halaman apa saja yang dapat diakses dan aksi apa yang diizinkan di dalam CMS dan classroom.

---

### 3. CMS (Admin Panel)

CMS adalah area khusus untuk pengelolaan bisnis, hanya dapat diakses oleh user dengan role tertentu:

- `admin` & `superadmin` → akses penuh ke modul CMS.
- `mentor` → akses terbatas (sesuai tanggung jawab pengajaran).
- `peserta` → tidak memiliki akses ke CMS.

#### 3.1 Overview Bisnis

- Ringkasan data penting (bergantung implementasi), seperti:
  - Jumlah user.
  - Jumlah kelas.
  - Ringkasan order dan status pembayaran.
  - dan lain lain.
- Menjadi entry point navigasi ke modul-modul lain di CMS.

#### 3.2 Manajemen User & Role

- **List semua user** dengan atribut:
  - Nama, email, role.
- Fitur:
  - Update role user antara:
    - `peserta`, `mentor`, `admin`, `superadmin`.
  - Aturan proteksi:
    - User tidak dapat mengubah role dirinya sendiri.
    - User dengan role lebih rendah tidak bisa mengubah role `superadmin`.
    - Hanya `superadmin` yang dapat mengubah role `superadmin`.

#### 3.3 CRUD Konten Landing Page

- Mengelola elemen-elemen yang tampil di landing page:

  - **Kurikulum** – daftar mata kuliah/modul per semester.
  - **Testimonials** – testimoni dari peserta.
  - **Mentors** – profil mentor yang akan ditampilkan ke publik.
  - **dsb**

- Fitur:
  - Tambah / edit / hapus data.
  - Kontrol **visibility** (tampil / disembunyikan di landing).

#### 3.4 CRUD Kelas (Catalog Kelas untuk Order)

- Mengelola **daftar kelas** yang akan muncul di katalog dan dapat dipesan oleh peserta.

- Atribut utama kelas:
  - Judul kelas.
  - Deskripsi.
  - Relasi ke satu atau lebih mentor.
  - Relasi ke satu atau lebih item kurikulum.
  - Harga.
  - Status visibilitas (tampil/tidak di landing dan daftar kelas).

Kelas inilah yang nantinya dipakai di:

- Halaman **/daftar-kelas**.
- Modul **order & pembayaran**.
- Enrollments peserta.

#### 3.5 Fitur Order & Pembayaran Manual

Sistem pembayaran dibuat manual namun terstruktur:

1. Peserta memilih satu atau beberapa kelas dan memasukkan ke **keranjang**.
2. Peserta melakukan **checkout**.
3. Sistem menampilkan **nomor rekening** untuk transfer pembayaran.
4. Peserta melakukan transfer dan mengunggah **bukti transfer**.
5. Order masuk dengan status `pending` dan menunggu validasi admin.

#### 3.6 List Order Masuk & Manajemen Status

Modul untuk admin/superadmin memantau dan memproses order:

- Menampilkan daftar order masuk dengan:
  - Waktu order.
  - Nama/email user.
  - Nama pengirim di slip (jika diisi).
  - Total pembayaran.
  - Link bukti transfer.
  - Catatan tambahan (jika ada).
  - Status order:
    - `pending`
    - `approved`
    - `rejected`
    - `expired`

- Aksi yang tersedia:

  - Untuk `pending`:
    - **Approve** → pembayaran diterima.
    - **Reject** → pembayaran ditolak.
  - Untuk `approved`:
    - **Expire** → menandai order sudah tidak aktif lagi (misalnya masa pembelajaran telah selesai).
  - Untuk `rejected` / `expired`:
    - Status bersifat final (non-aktif).

#### 3.7 CRUD Mentor & Materi Classroom

- Admin dapat mengelola daftar mentor:
  - Tambah/edit/hapus data mentor.
  - Menandai mentor yang tampil di landing.
- Mentor terkait kemudian dapat:
  - Mengupload materi.
  - Mengupload rekaman/recording.
- Materi dan rekaman ini akan muncul di **classroom peserta** untuk kelas yang terhubung.

#### 3.8 Enrollments (Akses Kelas Peserta)

- Modul untuk mengelola **enrollment** peserta ke kelas:

  - Admin menentukan secara manual:
    - Peserta X ter-enroll/aktif di kelas apa saja.

- Hubungan antara order dan enrollment:

  - Order yang sudah `approved` menjadikan peserta eligible.
  - Admin kemudian mengatur kelas apa saja yang benar-benar diaktifkan untuk peserta tersebut.

- Dampak langsung:
  - Daftar kelas yang terlihat di halaman `/peserta` untuk setiap user ditentukan oleh data enrollments ini.

#### 3.9 List Feedback Peserta

- Modul untuk menampilkan **feedback** yang masuk dari peserta:

  - Feedback bersifat anonim pada level CMS.
  - Bisa difilter berdasarkan kelas.

- Informasi yang ditampilkan:
  - Nama kelas.
  - Tanggal feedback.
  - Rating (jika ada).
  - Teks feedback.

- Admin / superadmin dapat:
  - Menghapus feedback yang tidak relevan atau tidak pantas.

---

### 4. Halaman Peserta & Kelas

#### 4.1 `/daftar-kelas` – Katalog Kelas

- Halaman untuk peserta melihat dan memilih kelas yang tersedia.
- Menggunakan data dari kelas yang:
  - `visible = true`.
- Dari sini peserta:
  - Melihat informasi singkat kelas.
  - Menambahkan kelas ke keranjang.
  - Melanjutkan ke proses order & pembayaran manual.

#### 4.2 `/peserta` – Classroom Peserta

- Halaman khusus peserta setelah login.
- Menampilkan:
  - Daftar kelas yang telah di-enroll untuk peserta tersebut (berdasarkan pengaturan enrolment admin).
  - Materi dan rekaman yang diupload mentor untuk tiap kelas.
- Peserta dapat:
  - Mengakses materi & recording.
  - Mengirim feedback terkait kelas.

---

## Teknologi

### Frontend

- **Next.js** (App Router)
- **React** + **TypeScript**
- **Tailwind CSS**
- Komponen UI kustom:
  - Button, Modal, ConfirmModal, dsb.

### Backend

> Backend berjalan terpisah dari repository frontend ini.

- **FastAPI** (Python) sebagai REST API.
- Endpoint utama:
  - Autentikasi & `/me`.
  - Manajemen user & role.
  - Classes, curriculum, mentors.
  - Orders & pembayaran.
  - Enrollments.
  - Testimonials & feedback.
  - dsb.

---

## Arsitektur & Struktur Proyek (Frontend)

Struktur direktori utama (disederhanakan):

```txt
src/
  app/
    page.tsx                 # landing page
    daftar-kelas/            # katalog kelas peserta
    peserta/                 # classroom peserta
    cms/
      page.tsx               # overview CMS
      user-role/
      users/
      classes/
      mentors/
      curriculum/
      orders/
      testimonials/
      enrollments/
      feedback/

  lib/
    admin.ts                 # API & tipe terkait user / role / me
    classes.ts               # API & tipe kelas
    curriculum.ts            # API & tipe curriculum
    mentors.ts               # API & tipe mentor
    orders.ts                # API & tipe order
    feedback.ts              # API & tipe feedback
    ...                      # modul domain lain
  hooks/
    useClasses.ts
    useMentors.ts
    useOrders.ts
    useFeedback.ts
    useEnrollments.ts
    ...                      # custom hooks lain
  components/
    ui/
      Button.tsx
      Modal.tsx
      ConfirmModal.tsx
      ...
```

### Prinsip yang dipakai

Proyek ini mengikuti pola pemisahan tanggung jawab yang jelas agar mudah dikembangkan dan dirawat:

- **`lib/`**  
  Menyimpan **definisi tipe** dan **fungsi API per domain** (misalnya: `admin`, `classes`, `curriculum`, `mentors`, `orders`, `feedback`, dan lain-lain).  
  Direktori ini menjadi _single source of truth_ untuk komunikasi frontend ↔ backend.

- **`hooks/`**  
  Berisi **custom hooks** yang mengenkapsulasi:
  - data fetching,
  - state & error handling,
  - transformasi data yang berhubungan dengan UI.

- **`app/.../components/`**  
  Fokus pada **presentational & container components**:
  - `SomethingPage.tsx` → container per fitur (menghubungkan hooks & komponen UI),
  - komponen kecil seperti `Header`, `Table`, `List`, dan lainnya yang reusable.

- **`app/.../page.tsx`**  
  Sangat tipis, hanya merender satu komponen kontainer per route:
  - Memudahkan pembacaan struktur route Next.js,
  - Menghindari `page.tsx` yang penuh logic dan sulit dirawat.

Dengan pola ini, domain bisnis (orders, feedback, enrollments, dan lain-lain) tidak bercampur dengan detail tampilan, sehingga refactor maupun penambahan fitur baru lebih aman dan terstruktur.

---

## Menjalankan Secara Lokal

> Catatan: frontend dan backend berada di repo/layanan terpisah. Pastikan backend FastAPI sudah berjalan sebelum menjalankan frontend.

### 1. Prasyarat

- FASTAPI
- Package manager:
  - **pip**, **uvicorn**, atau **py**
- Backend FastAPI aktif, misalnya di:

```txt
http://localhost:8000
```

### 2. Konfigurasi Environment

Buat file `.env.local` di root project:

```bash
APP_ENV=dev
APP_HOST=0.0.0.0
APP_PORT=8000
APP_ORIGIN=http://localhost:3000

JWT_SECRET=xxx
JWT_ALG=HS256
JWT_EXPIRES_MIN=120

SUPABASE_URL=xxx
SUPABASE_SERVICE_ROLE_KEY=xxx

PAYMENTS_BUCKET=payments
BANK_NAME=xxx
BANK_ACCOUNT=xxx
BANK_HOLDER=xxx
GROUP_LINK=xxx

```

Ubah nilai tersebut jika backend berjalan pada host/port yang berbeda.

### 3. Instal Dependensi

```bash
pip install -r requirements.txt
```

### 4. Jalankan Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Aplikasi dapat diakses di:

```txt
http://localhost:8000
```

---

## Peran User & Akses

### Peserta

- Registrasi dan login.
- Melihat landing page dan `/daftar-kelas`.
- Memilih kelas, checkout, dan mengunggah bukti transfer.
- Mengakses classroom di `/peserta` (hanya kelas yang sudah di-enroll).
- Mengirim feedback untuk kelas yang diikuti.

### Mentor

- Login ke CMS.
- Melihat kelas yang menjadi tanggung jawabnya.
- Mengunggah materi dan rekaman kelas.
- Membantu menyediakan konten untuk classroom peserta.

### Admin

- Memiliki semua hak peserta dan mentor.
- Mengelola:
  - Konten landing page (kurikulum, testimonial, mentor, dsb.).
  - Daftar kelas & katalog untuk order.
  - Order & pembayaran:
    - Approve / reject / expire.
  - Enrollments:
    - Menentukan peserta terdaftar di kelas mana saja.
  - Feedback:
    - Melihat dan menghapus feedback yang tidak relevan.

### Superadmin

- Memiliki semua hak admin.
- Hak tambahan:
  - Mengelola role user lain (termasuk admin dan mentor).
  - Proteksi khusus:
    - Hanya superadmin yang dapat mengubah role superadmin lain.

---

## Alur Bisnis Singkat

1. **Setup awal oleh admin/superadmin**
   - Menambahkan kurikulum, mentor, kelas, dan konten landing page.

2. **Peserta mendaftar & login**
   - Membuat akun dan masuk ke sistem.
   - Melihat daftar kelas di `/daftar-kelas`.

3. **Peserta melakukan order**
   - Memilih kelas → dimasukkan ke keranjang → checkout.
   - Mendapat nomor rekening dan instruksi transfer.
   - Mengunggah bukti transfer.

4. **Admin memvalidasi pembayaran**
   - Order berstatus `pending`.
   - Admin dapat:
     - **Approve** → pembayaran diterima.
     - **Reject** → pembayaran ditolak.

5. **Admin mengatur Enrollments**
   - Menentukan peserta X aktif pada kelas A/B/C.
   - Berpengaruh langsung pada daftar kelas yang muncul di `/peserta`.

6. **Peserta mengikuti kelas**
   - Mengakses materi & rekaman yang diunggah mentor di classroom.
   - Mengirim feedback melalui interface yang disediakan.

7. **Admin memantau feedback**
   - Menggunakan modul feedback di CMS untuk evaluasi kualitas kelas dan peningkatan program ke depannya.

---

## Lisensi

Proyek ini digunakan sebagai **aplikasi internal bisnis** TC Mudah dan tidak dimaksudkan sebagai perangkat lunak open source umum.

Struktur kode, arsitektur, dan penerapan praktik _clean architecture_ di frontend (Next.js + TypeScript) menjadikan proyek ini layak dijadikan **portofolio profesional**, menunjukkan kemampuan:

- merancang sistem berbasis role & CMS,
- mengintegrasikan frontend–backend secara terstruktur,
- dan mengelola fitur bisnis yang kompleks dalam codebase yang tetap rapi dan maintainable.
