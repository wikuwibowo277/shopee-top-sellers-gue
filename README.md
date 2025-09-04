
# Shopee Top Sellers — Apify Connected (Streamlit MVP+)

Aplikasi ini terhubung ke **Apify API**: jalankan actor → tarik dataset → tampilkan leaderboard.
Kamu cukup memasukkan **API Token** dan parameter seperti **negara, keyword, kategori, harga**.

## Cara Menjalankan (paling mudah)
1. Buka https://streamlit.io → Community Cloud → Deploy an app
2. Upload `app.py` dan `requirements.txt` (atau push ke GitHub)
3. Jalankan. Masukkan **API Token Apify**, `actor_id`, dan parameter → klik **Run**.

## Catatan
- Nama input `payload` mengikuti actor default (contoh umum: country, keyword, categoryId, minPrice, maxPrice, limit).
- Tidak semua actor identik. Jika actor berbeda, sesuaikan field input.
- 'Per bulan/Per tahun' memerlukan **snapshot berkala** (jadwalkan run harian → bandingkan delta).

## Keamanan
- Simpan token di sidebar (session) saat session aktif. Reset saat refresh. Jangan bagikan token.
