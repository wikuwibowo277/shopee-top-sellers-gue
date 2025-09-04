
import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
from urllib.parse import urlencode

st.set_page_config(page_title="Shopee Top Sellers via Apify", layout="wide")
st.title("🛒 Shopee Top Sellers — Terhubung Apify (MVP+)")

st.markdown("""
Aplikasi ini akan **menjalankan actor di Apify**, lalu otomatis **mengambil dataset** hasil scrape untuk
ditampilkan sebagai **leaderboard produk terlaris**.  
Kamu cukup masukkan **API Token Apify** dan parameter pencarian (keyword/kategori/negara/harga).  
""")

with st.sidebar:
    st.header("🔑 Apify")
    token = st.text_input("API Token Apify", type="password", help="Dari Apify Console → Integrations → API Token")
    st.caption("Token tidak berubah otomatis. Kamu bisa reset/revoke di Apify kapan saja.")
    st.divider()
    st.header("⚙️ Actor")
    actor_id = st.text_input("Actor ID (acts/{username}~{actorName})", value="apify/actor-shopee-scraper", help="Contoh: apify/actor-shopee-scraper atau pengguna lain")
    st.caption("Jika kamu punya Task ID, bisa gunakan endpoint Task juga di versi lanjutan.")

st.subheader("🎛️ Parameter Pencarian")
col1, col2, col3 = st.columns(3)
with col1:
    country = st.selectbox("Negara", ["ID","MY","SG","TH","PH","VN"], index=0)
    keyword = st.text_input("Keyword / Nama Produk (opsional)", value="")
with col2:
    price_min = st.text_input("Harga minimal (opsional)", value="", help="Contoh: 10000")
    price_max = st.text_input("Harga maksimal (opsional)", value="", help="Contoh: 500000")
with col3:
    category_id = st.text_input("Category ID Shopee (opsional)", value="", help="Biarkan kosong jika pakai keyword saja")
    limit = st.slider("Ambil berapa item (limit)", 20, 300, 120, 20)

st.caption("Catatan: Tidak semua actor mendukung semua parameter. Aktor yang berbeda bisa memiliki nama field input berbeda.")

st.subheader("⏱️ Opsi Periode (sesuai data yang tersedia)")
period = st.selectbox("Pilih Periode Analisis", ["Historical (total)","Per bulan (jika tersedia)","Per tahun (jika tersedia)"])
st.caption("Shopee umumnya menyediakan **historical_sold** (total). Analisis per-bulan/per-tahun memerlukan snapshot berkala atau actor yang memang menyediakan agregasi waktu.")

st.divider()

# Utilitas
def normalize_price(x):
    if pd.isna(x):
        return np.nan
    try:
        x = float(x)
        if x > 1e9:   # fallback jika tersimpan dalam satuan 'sen'
            return x/100000
        elif x > 1e6:
            return x/1000
        else:
            return x
    except Exception:
        return np.nan

def pick_col(df, keys):
    for k in keys:
        for c in df.columns:
            if k(c.lower()):
                return c
    return None

def run_apify_actor(token: str, actor_id: str, payload: dict):
    """Jalankan actor dan kembalikan (run_id, dataset_id) bila berhasil start."""
    url = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={token}"
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json().get("data", {})
    run_id = data.get("id")
    dataset_id = data.get("defaultDatasetId")
    status = data.get("status")
    return run_id, dataset_id, status

def poll_run(token: str, run_id: str, wait_sec=5, max_wait=300):
    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={token}"
    start = time.time()
    while True:
        r = requests.get(status_url, timeout=30)
        r.raise_for_status()
        data = r.json().get("data", {})
        status = data.get("status")
        if status in ("SUCCEEDED","FAILED","TIMED-OUT","ABORTED"):
            return status, data.get("defaultDatasetId")
        if time.time() - start > max_wait:
            return "TIMEOUT", data.get("defaultDatasetId")
        time.sleep(wait_sec)

def fetch_items(dataset_id: str, clean=True, limit=None):
    base = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
    params = {"clean": "true"} if clean else {}
    if limit:
        params["limit"] = limit
    url = base + "?" + urlencode(params)
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    items = r.json()
    if isinstance(items, dict) and "items" in items:
        items = items["items"]
    df = pd.json_normalize(items)
    return df

# Bangun payload umum
payload = {
    "country": country,
    "keyword": keyword or None,
    "categoryId": int(category_id) if category_id.strip().isdigit() else None,
    "minPrice": int(price_min) if price_min.strip().isdigit() else None,
    "maxPrice": int(price_max) if price_max.strip().isdigit() else None,
    "limit": int(limit)
}
payload = {k:v for k,v in payload.items() if v is not None}

colA, colB = st.columns([1,2])
with colA:
    run = st.button("🚀 Jalankan & Ambil Data")

if run:
    if not token:
        st.error("Mohon isi API Token Apify terlebih dahulu.")
        st.stop()
    try:
        with st.spinner("Menjalankan actor di Apify..."):
            run_id, ds_id_seed, status = run_apify_actor(token, actor_id, payload)
        st.success(f"Run dimulai: {run_id} (status: {status})")

        with st.spinner("Menunggu proses selesai..."):
            status_final, dataset_id = poll_run(token, run_id)
        st.info(f"Status akhir: {status_final}")
        if status_final != "SUCCEEDED":
            st.error("Run tidak berhasil. Coba cek actor_id, token, atau payload.")
            st.stop()

        ds_id = dataset_id or ds_id_seed
        if not ds_id:
            st.error("Dataset ID tidak ditemukan dari hasil run.")
            st.stop()

        with st.spinner("Mengambil dataset items..."):
            df = fetch_items(ds_id, clean=True, limit=None)
        st.success(f"Dataset berhasil dimuat. Baris: {len(df)}")

        # Normalisasi kolom penting
        col_title = pick_col(df, [lambda s: "title" in s or "name" in s])
        col_sold  = pick_col(df, [lambda s: "historical_sold" in s or s=="sold" or "sold" in s])
        col_rating= pick_col(df, [lambda s: "rating_star" in s or s=="rating"])
        col_rev   = pick_col(df, [lambda s: "rating_count" in s or "review" in s])
        col_pmin  = pick_col(df, [lambda s: "price_min" in s or s=="price"])
        col_pmax  = pick_col(df, [lambda s: "price_max" in s])
        col_shop  = pick_col(df, [lambda s: "shop_name" in s or "seller" in s or "shop" in s])
        col_loc   = pick_col(df, [lambda s: "shop_location" in s or s=="location"])
        col_url   = pick_col(df, [lambda s: "url" in s or "link" in s])

        rename = {}
        if col_title: rename[col_title] = "title"
        if col_sold:  rename[col_sold]  = "historical_sold"
        if col_rating:rename[col_rating]= "rating"
        if col_rev:   rename[col_rev]   = "reviews"
        if col_pmin:  rename[col_pmin]  = "price_min"
        if col_pmax:  rename[col_pmax]  = "price_max"
        if col_shop:  rename[col_shop]  = "shop"
        if col_loc:   rename[col_loc]   = "location"
        if col_url:   rename[col_url]   = "url"

        df = df.rename(columns=rename)

        # Bersihkan harga & rating
        if "price_min" in df.columns:
            df["price_min"] = pd.to_numeric(df["price_min"], errors="coerce").apply(normalize_price)
        if "price_max" in df.columns:
            df["price_max"] = pd.to_numeric(df["price_max"], errors="coerce").apply(normalize_price)
        if "rating" in df.columns:
            df["rating"] = pd.to_numeric(df["rating"], errors="coerce")

        # Ranking historis
        if "historical_sold" in df.columns:
            df["historical_sold"] = pd.to_numeric(df["historical_sold"], errors="coerce").fillna(0)
            df_ranked = df.sort_values("historical_sold", ascending=False).copy()
        else:
            df_ranked = df.copy()

        with st.sidebar:
            st.header("🔎 Filter Hasil")
            min_sold = st.number_input("Min. sold", value=0, step=10)
            min_rating = st.slider("Min. rating", 0.0, 5.0, 0.0, 0.1)
            f_min = st.number_input("Harga minimal", value=0, step=1000)
            f_max = st.number_input("Harga maksimal (0=tanpa batas)", value=0, step=1000)
            top_n = st.slider("Tampilkan Top N", 10, 300, 100, 10)

        def apply_filters(dfv):
            out = dfv.copy()
            if "historical_sold" in out.columns:
                out = out[out["historical_sold"].fillna(0) >= min_sold]
            if "rating" in out.columns:
                out = out[out["rating"].fillna(0) >= min_rating]
            if "price_min" in out.columns:
                out = out[out["price_min"].fillna(0) >= f_min]
            if "price_max" in out.columns and f_max > 0:
                out = out[out["price_max"].fillna(0) <= f_max]
            return out

        df_view = apply_filters(df_ranked)

        show_cols = [c for c in ["title","price_min","price_max","rating","reviews","historical_sold","shop","location","url"] if c in df_view.columns]
        st.subheader("📈 Leaderboard Produk")
        st.dataframe(df_view[show_cols].head(top_n), use_container_width=True)

        csv = df_view[show_cols].head(top_n).to_csv(index=False).encode("utf-8")
        st.download_button("💾 Download CSV (Top N)", data=csv, file_name="shopee_top_sellers.csv", mime="text/csv")

        st.info("Periode 'Per bulan/Per tahun' memerlukan dataset berseri (snapshot berkala). Kita bisa jadwalkan run harian lalu hitung delta.")

    except requests.HTTPError as e:
        st.error(f"HTTP Error: {e}")
    except Exception as e:
        st.error(f"Gagal menjalankan integrasi: {e}")
