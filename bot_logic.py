import csv
import os
import re
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from rag_core import llm, answer

# ---------- خط قرمزها (عمداً حساس؛ هشدار اضافی بهتر از هشدار از دست رفته) ----------
RED_FLAGS = [
    "درد قفسه", "درد سینه", "تنگی نفس", "نفسم", "سکته", "بیهوش", "غش کرد",
    "ضعف ناگهانی", "بی حسی ناگهانی", "فلج", "بی اختیاری", "کنترل ادرار",
    "کنترل مدفوع", "بی حسی بین پا", "بی حسی ناحیه تناسلی", "تب شدید",
    "تصادف", "سقوط", "ضربه شدید", "خونریزی شدید",
]
SELF_HARM = ["خودکشی", "خودمو بکشم", "خودم رو بکشم", "بکشم خودمو", "نمی خوام زنده باشم"]

EMERGENCY_REPLY = (
    "⚠️ علائمی که توضیح دادید ممکنه فوری باشه. لطفاً همین الان با اورژانس (۱۱۵) تماس بگیرید "
    "یا به نزدیک‌ترین مرکز اورژانس مراجعه کنید و منتظر نوبت مطب نمونید. "
    "موضوع رو به تیم مطب هم اطلاع دادم."
)
SELF_HARM_REPLY = (
    "خیلی متأسفم که این‌قدر سختی می‌کشید و ممنونم که گفتید. لطفاً تنها نمونید: همین الان با یک نفر "
    "مورد اعتمادتون صحبت کنید یا با اورژانس (۱۱۵) تماس بگیرید. موضوع رو به تیم مطب هم اطلاع دادم."
)


def normalize(text: str) -> str:
    text = text.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def to_en_digits(s: str) -> str:
    return s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "0123456789" * 2))


# ---------- طبقه‌بندی با LLM ----------
classify_prompt = ChatPromptTemplate.from_template("""
پیام بیمار را دقیقاً در یکی از این دسته‌ها قرار بده و فقط یک کلمه‌ی انگلیسی بنویس:
emergency: علائم خطرناک یا فوری (درد قفسه سینه، تنگی نفس، ضعف یا بی‌حسی ناگهانی، بی‌اختیاری ادرار/مدفوع)
appointment: می‌خواهد نوبت بگیرد، تغییر دهد یا لغو کند
complaint: شکایت یا نارضایتی
medical: سؤال درباره‌ی درد، علائم یا درمان
general: ساعت کاری، آدرس، هزینه، خدمات و اطلاعات عمومی مطب

پیام: {text}
""")
classify_chain = classify_prompt | llm | StrOutputParser()


def classify(text: str) -> str:
    out = classify_chain.invoke({"text": text}).strip().lower()
    for label in ("emergency", "appointment", "complaint", "medical", "general"):
        if label in out:
            return label
    return "general"


# ---------- جریان ثبت نوبت ----------
sessions = {}
APPT_FILE = "appointments.csv"

import csv
import os
import re
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# تنظیمات اتصال به گوگل شیت
SHEET_NAME = "Clinic Appointments"
KEY_FILE = "google_key.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_sheet():
    """اتصال به گوگل شیت با کلید Service Account"""
    if not os.path.exists(KEY_FILE):
        return None
    creds = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

def save_appointment(data: dict):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    row = [
        now_str,
        data["name"],
        data["phone"],
        data["time"],
        data["reason"],
        "در انتظار تأیید منشی"
    ]
    
    # 1. تلاش برای ثبت در گوگل شیت
    saved_to_cloud = False
    try:
        sheet = get_sheet()
        if sheet:
            sheet.append_row(row)
            saved_to_cloud = True
            print("Appointment successfully saved to Google Sheets.")
    except Exception as e:
        print(f"Error saving to Google Sheets: {e}")

    # 2. ذخیره محلی در CSV به عنوان پشتیبان (یا در صورت قطعی اینترنت)
    new_file = not os.path.exists(APPT_FILE)
    with open(APPT_FILE, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["زمان ثبت", "نام", "موبایل", "زمان دلخواه", "دلیل مراجعه", "وضعیت"])
        w.writerow(row)


# def save_appointment(data: dict):
#     new_file = not os.path.exists(APPT_FILE)
#     with open(APPT_FILE, "a", newline="", encoding="utf-8-sig") as f:
#         w = csv.writer(f)
#         if new_file:
#             w.writerow(["زمان ثبت", "نام", "موبایل", "زمان دلخواه", "دلیل مراجعه", "وضعیت"])
#         w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), data["name"], data["phone"],
#                     data["time"], data["reason"], "در انتظار تأیید منشی"])


def handle_appointment(uid, text):
    s = sessions[uid]
    t = text.strip()
    if t in ("لغو", "انصراف"):
        sessions.pop(uid)
        return "درخواست نوبت لغو شد. اگه کمک دیگه‌ای لازم دارید بفرمایید.", None

    step = s["step"]
    if step == "name":
        s["data"]["name"] = t
        s["step"] = "phone"
        return "ممنون. شماره موبایل‌تون رو بفرمایید؟ (مثلاً 09123456789)", None
    if step == "phone":
        p = to_en_digits(t)
        if not re.fullmatch(r"09\d{9}", p):
            return "شماره معتبر نیست. لطفاً موبایل ۱۱ رقمی رو بفرمایید (مثلاً 09123456789).", None
        s["data"]["phone"] = p
        s["step"] = "time"
        return "چه روز و ساعتی براتون مناسبه؟ (شنبه تا چهارشنبه، ۱۶ تا ۲۰)", None
    if step == "time":
        s["data"]["time"] = t
        s["step"] = "reason"
        return "دلیل مراجعه یا محل درد رو در یک جمله بفرمایید.", None
    if step == "reason":
        s["data"]["reason"] = t
        s["step"] = "confirm"
        d = s["data"]
        return (f"لطفاً تأیید کنید:\nنام: {d['name']}\nموبایل: {d['phone']}\n"
                f"زمان دلخواه: {d['time']}\nدلیل: {d['reason']}\n\nثبت بشه؟ (بله / لغو)"), None
    if step == "confirm":
        if t in ("بله", "تایید", "تأیید", "آره", "ثبت"):
            d = sessions.pop(uid)["data"]
            save_appointment(d)
            alert = (
                f"📅 درخواست نوبت جدید\n"
                f"👤 نام: {d['name']}\n"
                f"📞 موبایل: {d['phone']}\n"
                f"⏰ زمان: {d['time']}\n"
                f"🩺 دلیل: {d['reason']}"
            )
            # علاوه بر متن هشدار، شناسه بیمار (uid) را هم برمی‌گردانیم
            return (
                "درخواست نوبت شما ثبت شد ✅ منشی برای تأیید نهایی زمان با شما هماهنگ می‌کنه.",
                {"text": alert, "patient_id": uid}
            )
        sessions.pop(uid)
        return "ثبت انجام نشد. هر وقت خواستید دوباره بفرمایید.", None


# ---------- نقطه‌ی ورود: خروجی = (پاسخ، هشدار برای منشی یا None) ----------
def handle_message(uid, text):
    norm = normalize(text)

    if any(k in norm for k in SELF_HARM):
        return SELF_HARM_REPLY, f"🚨 پیام حساس (افکار آسیب به خود) | کاربر {uid}: {text}"
    if any(k in norm for k in RED_FLAGS):
        return EMERGENCY_REPLY, f"🚨 خط قرمز | کاربر {uid}: {text}"

    if uid in sessions:
        return handle_appointment(uid, text)

    cat = classify(text)
    if cat == "emergency":
        return EMERGENCY_REPLY, f"🚨 خط قرمز (تشخیص مدل) | کاربر {uid}: {text}"
    if cat == "appointment":
        sessions[uid] = {"step": "name", "data": {}}
        return "حتماً. اسم و فامیل بیمار رو بفرمایید؟ (برای انصراف بنویسید «لغو»)", None
    if cat == "complaint":
        return ("از اینکه تجربه‌ی خوبی نداشتید متأسفم. پیام شما رو برای منشی فرستادم تا پیگیری کنن.",
                f"⚠️ شکایت | کاربر {uid}: {text}")
    return answer(text), None  # medical / general → RAG


if __name__ == "__main__":
    while True:
        q = input("پیام (خروج: q): ")
        if q.strip().lower() == "q":
            break
        reply, alert = handle_message("terminal", q)
        print(reply)
        if alert:
            print("--- هشدار برای منشی ---\n" + alert)
        print()