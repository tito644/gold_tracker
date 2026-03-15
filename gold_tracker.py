"""
Gold Price Tracker — الخطوة 2
================================
سكريبت بيجيب سعر الذهب من gold-api.com
وبيخزنه في SQLite database محلية.

المتطلبات:
    pip install requests

تشغيل:
    python gold_tracker.py
"""

import requests
import sqlite3
import time
from datetime import datetime


# ───────────────────────────────────────
# 1. إعدادات عامة
# ───────────────────────────────────────
API_URL   = "https://api.gold-api.com/price/XAU"
DB_FILE   = "gold_prices.db"
HEADERS   = {"User-Agent": "GoldTracker/1.0"}


# ───────────────────────────────────────
# 2. إنشاء قاعدة البيانات (مرة واحدة بس)
# ───────────────────────────────────────
def init_db():
    """بتنشئ الـ table لو مش موجودة."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gold_prices (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            fetched_at     TEXT    NOT NULL,          -- وقت الجلب (UTC)
            price_usd      REAL    NOT NULL,          -- سعر الأونصة بالدولار
            price_gram_24k REAL,                      -- جرام عيار 24
            price_gram_22k REAL,                      -- جرام عيار 22
            price_gram_21k REAL,                      -- جرام عيار 21
            price_gram_18k REAL,                      -- جرام عيار 18
            change_usd     REAL,                      -- التغيير بالدولار
            change_pct     REAL,                      -- التغيير بالنسبة %
            source         TEXT DEFAULT 'gold-api.com'
        )
    """)
    conn.commit()
    conn.close()
    print("✓ قاعدة البيانات جاهزة:", DB_FILE)


# ───────────────────────────────────────
# 3. جلب البيانات من الـ API
# ───────────────────────────────────────
def fetch_gold_price():
    """بتطلب السعر من الـ API وبترجع dict أو None لو في مشكلة."""
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        response.raise_for_status()          # بترفع exception لو status مش 200
        return response.json()
    except requests.exceptions.ConnectionError:
        print("✗ مشكلة في الاتصال بالإنترنت")
    except requests.exceptions.Timeout:
        print("✗ الـ API مردتش في الوقت المحدد")
    except requests.exceptions.HTTPError as e:
        print(f"✗ HTTP Error: {e}")
    except Exception as e:
        print(f"✗ خطأ غير متوقع: {e}")
    return None


# ───────────────────────────────────────
# 4. تنظيف البيانات
# ───────────────────────────────────────
def clean_data(raw: dict) -> dict:
    """بتتأكد إن البيانات سليمة وبتحسبها لو ناقصة."""

    def safe_float(val, default=None):
        """بتحول أي قيمة لـ float بأمان."""
        try:
            return float(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    price = safe_float(raw.get("price"))
    if not price:
        raise ValueError("مفيش سعر في الـ response!")

    # لو الـ API مرجعش سعر الجرام، بنحسبه إحنا
    # 1 troy ounce = 31.1035 grams
    oz_to_gram = price / 31.1035
    gram_24k = safe_float(raw.get("price_gram_24k")) or round(oz_to_gram, 2)
    gram_22k = safe_float(raw.get("price_gram_22k")) or round(oz_to_gram * (22/24), 2)
    gram_21k = safe_float(raw.get("price_gram_21k")) or round(oz_to_gram * (21/24), 2)
    gram_18k = safe_float(raw.get("price_gram_18k")) or round(oz_to_gram * (18/24), 2)

    return {
        "fetched_at":     datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "price_usd":      round(price, 2),
        "price_gram_24k": gram_24k,
        "price_gram_22k": gram_22k,
        "price_gram_21k": gram_21k,
        "price_gram_18k": gram_18k,
        "change_usd":     safe_float(raw.get("ch")),
        "change_pct":     safe_float(raw.get("chp")),
    }


# ───────────────────────────────────────
# 5. حفظ في قاعدة البيانات
# ───────────────────────────────────────
def save_to_db(data: dict):
    """بتحفظ الـ record في الـ SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        INSERT INTO gold_prices
            (fetched_at, price_usd, price_gram_24k, price_gram_22k,
             price_gram_21k, price_gram_18k, change_usd, change_pct)
        VALUES
            (:fetched_at, :price_usd, :price_gram_24k, :price_gram_22k,
             :price_gram_21k, :price_gram_18k, :change_usd, :change_pct)
    """, data)
    conn.commit()
    conn.close()


# ───────────────────────────────────────
# 6. عرض النتيجة في الـ Terminal
# ───────────────────────────────────────
def print_result(data: dict):
    """بتطبع النتيجة بشكل واضح."""
    chp = data["change_pct"]
    arrow = "▲" if (chp or 0) >= 0 else "▼"
    sign  = "+" if (chp or 0) >= 0 else ""

    print("\n" + "─" * 42)
    print(f"  🥇 Gold Price — {data['fetched_at']} UTC")
    print("─" * 42)
    print(f"  الأونصة   : ${data['price_usd']:>10,.2f}")
    print(f"  جرام 24k  : ${data['price_gram_24k']:>10,.2f}")
    print(f"  جرام 22k  : ${data['price_gram_22k']:>10,.2f}")
    print(f"  جرام 21k  : ${data['price_gram_21k']:>10,.2f}")
    print(f"  جرام 18k  : ${data['price_gram_18k']:>10,.2f}")
    if chp is not None:
        print(f"  التغيير   : {arrow} {sign}{chp:.2f}%  (${sign}{data['change_usd']:.2f})")
    print("─" * 42)
    print("  ✓ تم الحفظ في gold_prices.db\n")


# ───────────────────────────────────────
# 7. Main — نقطة التشغيل
# ───────────────────────────────────────
def run():
    print("🚀 Gold Price Tracker — بيشتغل...")

    # إنشاء الـ DB
    init_db()

    # جلب البيانات
    raw = fetch_gold_price()
    if raw is None:
        print("✗ فشل الجلب — هيجرب تاني بعد 5 ثواني")
        time.sleep(5)
        raw = fetch_gold_price()
        if raw is None:
            print("✗ فشل مرتين — خروج")
            return

    # تنظيف
    try:
        data = clean_data(raw)
    except ValueError as e:
        print(f"✗ خطأ في البيانات: {e}")
        return

    # حفظ
    save_to_db(data)

    # عرض
    print_result(data)


if __name__ == "__main__":
    run()
