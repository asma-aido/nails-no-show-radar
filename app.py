import random
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st


# بيانات اختبر عليها المنتج (صالون أظافر)
NAIL_SERVICES = [
    ("Manicure", 45, [70, 90, 110]),
    ("Pedicure", 60, [90, 120, 150]),
    ("Gel Polish", 60, [120, 150, 180]),
    ("Gel Extensions", 90, [200, 240, 280]),
    ("Acrylic Set", 120, [260, 320, 380]),
    ("Manicure + Pedicure", 105, [180, 220, 260]),
]

TECHS = ["Asma", "Hessa", "Aisha", "Razan"]


def generate_bookings_data(n: int = 35, seed: int = 7):
    random.seed(seed)
    now = datetime.now()
    out = []

    for i in range(n):
        hours_until = random.randint(1, 12)
        start_time = now + timedelta(hours=hours_until)

        service_name, duration_min, price_choices = random.choice(NAIL_SERVICES)
        price = random.choice(price_choices)

        created_hours_before = random.randint(1, 72)
        visits = random.randint(0, 12)

        past_no_shows = 0
        # بعض الزباين لهم سجل بسيط لعدم حضور المواعيد
        if random.random() < 0.15:
            past_no_shows = random.choice([1, 2])

        last_visit_days_ago = random.randint(3, 180)

        # وقت الذروة غالبًا بعد الدوام
        hour = start_time.hour
        is_peak_hour = 17 <= hour <= 21

        out.append(
            {
                "booking_id": i + 1,
                "customer_id": random.randint(1, 25),
                "start_time": start_time,
                "service": service_name,
                "duration_min": duration_min,
                "tech": random.choice(TECHS),
                "price": price,
                "created_hours_before": created_hours_before,
                "visits_count": visits,
                "past_no_shows": past_no_shows,
                "last_visit_days_ago": last_visit_days_ago,
                "is_peak_hour": is_peak_hour,
            }
        )

    return out


def calculate_risk_score(booking: dict) -> int:
    score = 0

    # أعلى علامة خطر: وجود سجل عدم حضور سابق
    if booking["past_no_shows"] >= 1:
        score += 40

    # العميل الجديد غالبًا أقل التزام
    if booking["visits_count"] == 0:
        score += 20

    # انقطاع طويل عن آخر زيارة
    if booking["last_visit_days_ago"] > 120:
        score += 10

    # الحجز المتأخر يعطي انطباع بعدم جدية
    if booking["created_hours_before"] < 3:
        score += 15

    # لا نريد ضياع مواعيد الجلسات الطويلة
    if booking["duration_min"] >= 90:
        score += 10

    # الذروة حساسة للسعة
    if booking["is_peak_hour"]:
        score += 10

    # لا نريد ضياع الجلسات الأعلى سعرًا
    if booking["price"] >= 240:
        score += 15

    return score


def risk_level(score: int) -> str:
    if score >= 65:
        return "High"
    if score >= 35:
        return "Medium"
    return "Low"


def suggested_action(booking: dict) -> str:
    risk = booking["risk"]
    price = booking["price"]
    hours_before = booking["created_hours_before"]
    duration = booking["duration_min"]
    is_peak = booking["is_peak_hour"]

    if risk == "High":
        # سياسة العربون: للجلسات الطويلة أو الأعلى سعرًا، أو في الذروة بشرط أن السعر مرتفع
        heavy = (duration >= 90) or (price >= 300) or (is_peak and price >= 240)

        if heavy:
            return "طلب عربون ثم تأكيد عبر واتساب"

        if hours_before <= 4:
            return "واتساب: الرجاء تأكيد الموعد (1 تأكيد / 0 اعتذار)"

        return "تأكيد إضافي عبر واتساب"

    if risk == "Medium":
        if is_peak:
            return "تذكير إضافي + تأكيد واتساب"
        return "تذكير إضافي"

    return "تذكير عادي"


def calculate_metrics(bookings: list[dict]) -> dict:
    total = len(bookings)
    high = [b for b in bookings if b["risk"] == "High"]

    revenue_at_risk = sum(b["price"] for b in high)
    minutes_at_risk = sum(b["duration_min"] for b in high)

    expected_reduction_high = 0.25
    expected_protected = int(revenue_at_risk * expected_reduction_high)

    return {
        "total_bookings": total,
        "high_risk_count": len(high),
        "revenue_at_risk": revenue_at_risk,
        "hours_at_risk": round(minutes_at_risk / 60, 1),
        "expected_protected": expected_protected,
    }


# --- UI ---
st.set_page_config(page_title="Nails No-Show Radar", layout="wide")
st.title("نظام تقليل عدم الحضور لمواعيد الأظافر (MVP)")
st.caption("يعرض مواعيد اليوم ويحدد المواعيد المعرضة لعدم الحضور مع إجراء مقترح")

st.sidebar.header("التحكم")
only_high = st.sidebar.checkbox("عرض عالي الخطورة فقط", value=False)
seed = st.sidebar.number_input("رقم التوليد (Seed)", min_value=1, max_value=999, value=7, step=1)
n = st.sidebar.slider("عدد المواعيد", 10, 80, 35)

bookings = generate_bookings_data(n=n, seed=seed)

for bk in bookings:
    s = calculate_risk_score(bk)
    bk["risk_score"] = s
    bk["risk"] = risk_level(s)
    bk["action"] = suggested_action(bk)

m = calculate_metrics(bookings)

df = pd.DataFrame(bookings)
df["start_time"] = df["start_time"].dt.strftime("%H:%M")
df = df.sort_values(by="start_time")

tabs = st.tabs(["لوحة اليوم", "منطق التقييم", "الأثر المتوقع"])


# --- Tab 1: Today ---
with tabs[0]:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("عدد مواعيد اليوم", m["total_bookings"])
    c2.metric("مواعيد عالية الخطورة", m["high_risk_count"])
    c3.metric("إيراد معرّض للخطر", f'{m["revenue_at_risk"]} ريال')
    c4.metric("ساعات معرّضة للخطر", f'{m["hours_at_risk"]} ساعة')
    c5.metric("إيراد متوقع حمايته", f'{m["expected_protected"]} ريال')

    st.subheader("مواعيد اليوم")

    show_df = df.copy()
    if only_high:
        show_df = show_df[show_df["risk"] == "High"]

    st.dataframe(
        show_df[
            [
                "start_time",
                "service",
                "tech",
                "duration_min",
                "price",
                "visits_count",
                "past_no_shows",
                "is_peak_hour",
                "risk",
                "risk_score",
                "action",
            ]
        ],
        use_container_width=True,
    )


# --- Tab 2: Risk logic ---
with tabs[1]:
    st.subheader("منطق تقييم احتمال عدم الحضور (نموذج أولي)")

    st.write(
        "يعتمد هذا النموذج الأولي على قواعد بسيطة وسهلة الفهم لأن الهدف هو البدء بمنطق واضح "
        "وقابل للتفسير، ثم تحسينه لاحقًا باستخدام بيانات فعلية من السجلات اليومية."
    )

    st.write(
        "اخترت قواعد واضحة بدل تعلم آلي لأننا في البداية نحتاج منطق يقدر الفريق والتاجر يفهمه بسرعة، "
        "ونقدر نعدله بسهولة قبل الانتقال لحلول أكثر تقدمًا."
    )

    st.markdown(
        """
**العوامل المستخدمة في التقييم**
- سجل عدم الحضور السابق (أقوى مؤشر)
- عميل جديد أو سابق
- مدة طويلة منذ آخر زيارة
- الحجز المتأخر قبل الموعد
- طول جلسة الأظافر
- وقت الذروة
- السعر الأعلى للخدمة
"""
    )

    st.caption("أمثلة سريعة للتوضيح فقط")

    examples = df.sample(n=min(3, len(df)), random_state=int(seed))[
        [
            "service",
            "duration_min",
            "price",
            "visits_count",
            "past_no_shows",
            "is_peak_hour",
            "risk_score",
            "risk",
            "action",
        ]
    ]
    st.dataframe(examples, use_container_width=True)

    st.write(
        "أول تجربة فعلية بسويها: مقارنة (طلب عربون) مقابل (تأكيد واتساب إضافي) للحجوزات عالية الخطورة، "
        "وقياس الفرق في نسبة عدم الحضور والإيراد المحفوظ."
    )


# --- Tab 3: Impact ---
with tabs[2]:
    st.subheader("تقدير الأثر المتوقع")

    st.write(
        "هذه محاكاة تقريبية لربط القرارات التشغيلية بالأثر المالي. "
        "النسب المستخدمة هنا افتراضات مبدئية وليست نتائج فعلية."
    )

    r_high = st.slider("نسبة تقليل عدم الحضور للحجوزات عالية الخطورة", 0.0, 0.7, 0.25, 0.05)
    r_med = st.slider("نسبة تقليل عدم الحضور للحجوزات متوسطة الخطورة", 0.0, 0.5, 0.12, 0.03)

    high_df = df[df["risk"] == "High"]
    med_df = df[df["risk"] == "Medium"]

    rev_high = high_df["price"].sum()
    rev_med = med_df["price"].sum()

    protected = int(rev_high * r_high + rev_med * r_med)

    colA, colB, colC = st.columns(3)
    colA.metric("إيراد عالي الخطورة", f"{int(rev_high)} ريال")
    colB.metric("إيراد متوسط الخطورة", f"{int(rev_med)} ريال")
    colC.metric("الإيراد المتوقع حمايته", f"{protected} ريال")

    st.caption(
        "الخطوة القادمة: إجراء تجربة فعلية (A/B test) لمقارنة طلب العربون مقابل التأكيد الإضافي عبر واتساب، "
        "واستبدال الافتراضات ببيانات حقيقية."
    )
