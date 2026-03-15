"""
Gold Price Tracker — الخطوة 3
================================
تحقق من الـ Database وأضف جدول الـ Alerts.

تشغيل:
    python db_setup.py
"""

import sqlite3
from datetime import datetime

DB_FILE = "gold_prices.db"


# ───────────────────────────────────────
# 1. فحص البيانات الموجودة
# ───────────────────────────────────────
def inspect_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # بيخلي النتائج تتعامل زي dict

    print("\n📊 البيانات المحفوظة في gold_prices:")
    print("─" * 60)

    rows = conn.execute("""
        SELECT id, fetched_at, price_usd, price_gram_21k, change_pct
        FROM gold_prices
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()

    if not rows:
        print("  لا يوجد بيانات بعد — شغّل gold_tracker.py أولاً")
    else:
        print(f"  {'ID':<4} {'الوقت':<22} {'الأونصة':>10} {'جرام 21k':>10} {'تغيير%':>8}")
        print("  " + "─" * 56)
        for r in rows:
            chp = r["change_pct"]
            arrow = "▲" if (chp or 0) >= 0 else "▼"
            print(
                f"  {r['id']:<4} "
                f"{r['fetched_at']:<22} "
                f"${r['price_usd']:>9,.2f} "
                f"${r['price_gram_21k']:>9,.2f} "
                f"{arrow}{abs(chp or 0):>6.2f}%"
            )

    total = conn.execute("SELECT COUNT(*) FROM gold_prices").fetchone()[0]
    print(f"\n  إجمالي السجلات: {total}")
    conn.close()


# ───────────────────────────────────────
# 2. إضافة جدول الـ Price Alerts
# ───────────────────────────────────────
def create_alerts_table():
    """
    جدول بيخزن قواعد التنبيه.
    مثال: نبّهني لو سعر الأونصة راح فوق $5,100
    """
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_alerts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at   TEXT NOT NULL,
            alert_type   TEXT NOT NULL,  -- 'above' أو 'below'
            threshold    REAL NOT NULL,  -- السعر المستهدف
            metric       TEXT NOT NULL,  -- 'price_usd' أو 'price_gram_21k'
            message      TEXT,           -- رسالة التنبيه
            triggered    INTEGER DEFAULT 0,   -- 0 = لسه, 1 = اتفعّل
            triggered_at TEXT                 -- وقت التفعيل
        )
    """)

    # ───────────────────────────────────
    # 3. إضافة جدول الـ Daily Summary
    # ───────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_summary (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_date TEXT NOT NULL UNIQUE,  -- التاريخ (YYYY-MM-DD)
            open_price   REAL,   -- أول سعر في اليوم
            close_price  REAL,   -- آخر سعر في اليوم
            high_price   REAL,   -- أعلى سعر
            low_price    REAL,   -- أقل سعر
            avg_price    REAL,   -- متوسط اليوم
            readings     INTEGER -- عدد القراءات
        )
    """)
    conn.commit()
    conn.close()
    print("\n✓ تم إنشاء جدول price_alerts")
    print("✓ تم إنشاء جدول daily_summary")


# ───────────────────────────────────────
# 4. إضافة تنبيه تجريبي
# ───────────────────────────────────────
def add_sample_alert():
    conn = sqlite3.connect(DB_FILE)

    # جيب آخر سعر
    row = conn.execute(
        "SELECT price_usd, price_gram_21k FROM gold_prices ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if not row:
        print("✗ مفيش بيانات لإضافة تنبيه تجريبي")
        conn.close()
        return

    current_price = row[0]

    # تنبيه لو السعر طلع 2% فوق السعر الحالي
    alert_threshold = round(current_price * 1.02, 2)

    conn.execute("""
        INSERT OR IGNORE INTO price_alerts
            (created_at, alert_type, threshold, metric, message)
        VALUES (?, 'above', ?, 'price_usd', ?)
    """, (
        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        alert_threshold,
        f"⚠️ سعر الذهب تجاوز ${alert_threshold:,.2f} للأونصة!"
    ))
    conn.commit()

    print(f"\n✓ تنبيه تجريبي: نبّهني لو السعر تجاوز ${alert_threshold:,.2f}")
    conn.close()


# ───────────────────────────────────────
# 5. فحص التنبيهات — بيشتغل مع كل جلب
# ───────────────────────────────────────
def check_alerts():
    """
    بتتحقق لو أي تنبيه اتحقق بناءً على آخر سعر.
    استدعيها في gold_tracker.py بعد كل save_to_db()
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row

    # آخر سعر
    latest = conn.execute("""
        SELECT price_usd, price_gram_21k, price_gram_24k
        FROM gold_prices ORDER BY id DESC LIMIT 1
    """).fetchone()

    if not latest:
        conn.close()
        return

    # تنبيهات لسه ما اتفعّلتش
    alerts = conn.execute("""
        SELECT * FROM price_alerts WHERE triggered = 0
    """).fetchall()

    triggered_count = 0
    for alert in alerts:
        current_val = latest[alert["metric"]]
        should_trigger = (
            (alert["alert_type"] == "above" and current_val >= alert["threshold"]) or
            (alert["alert_type"] == "below" and current_val <= alert["threshold"])
        )
        if should_trigger:
            conn.execute("""
                UPDATE price_alerts
                SET triggered = 1, triggered_at = ?
                WHERE id = ?
            """, (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), alert["id"]))
            print(f"\n🔔 تنبيه: {alert['message']}")
            triggered_count += 1

    if triggered_count:
        conn.commit()
    else:
        print("  لا يوجد تنبيهات مفعّلة دلوقتي")

    conn.close()


# ───────────────────────────────────────
# 6. عرض هيكل الـ Database كامل
# ───────────────────────────────────────
def show_schema():
    conn = sqlite3.connect(DB_FILE)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()

    print("\n🗄️  هيكل قاعدة البيانات:")
    print("─" * 40)
    for (table_name,) in tables:
        cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"\n  📋 {table_name}  ({count} سجل)")
        for col in cols:
            pk = " 🔑" if col[5] else ""
            print(f"     • {col[1]:<20} {col[2]}{pk}")
    conn.close()


# ───────────────────────────────────────
# Main
# ───────────────────────────────────────
if __name__ == "__main__":
    print("🗄️  إعداد قاعدة البيانات...")

    inspect_db()
    create_alerts_table()
    add_sample_alert()
    check_alerts()
    show_schema()

    print("\n✅ قاعدة البيانات جاهزة للخطوة 4 (GitHub Actions)\n")
