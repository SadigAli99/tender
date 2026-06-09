import os
import re
import html
import time
import hashlib
import requests
import xml.etree.ElementTree as ET

from datetime import date, timedelta

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from db import init_db, tender_exists, save_tender
from detail_parser import parse_tender_detail
from sources import ACTIVE_SOURCES
from ai_translate import translate_tender_to_az


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

MAX_SEND_PER_KEYWORD = int(os.getenv("MAX_SEND_PER_KEYWORD", 1))

# 450k RUB-dan aşağı tenderlər Telegram-a göndərilməyəcək
MIN_PRICE_RUB = 450_000

# Paylaşılma tarixi son 3 gün içində olmalıdır
MIN_PUBLISH_DATE = date.today() - timedelta(days=3)

# Son müraciət tarixi ən azı 3 gün sonra olmalıdır
MIN_DEADLINE_DATE = date.today() + timedelta(days=3)


def clean_value(value, default="Yoxdur"):
    if value is None:
        return default

    value = str(value).strip()

    if value == "":
        return default

    return value


def parse_date_from_text(value):
    if not value:
        return None

    text = str(value)

    match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)

    if not match:
        return None

    day, month, year = match.groups()

    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def is_old_publish_date(tender):
    publish_date_text = (
        tender.get("publish_date")
        or tender.get("published_at")
        or tender.get("date")
    )

    publish_date = parse_date_from_text(publish_date_text)

    # Paylaşılma tarixi tapılmırsa, göndərmirik
    if publish_date is None:
        return True

    return publish_date < MIN_PUBLISH_DATE


def is_deadline_too_close_or_missing(tender):
    deadline_text = (
        tender.get("application_end")
        or tender.get("deadline")
    )

    deadline_date = parse_date_from_text(deadline_text)

    # Son tarix tapılmırsa, göndərmirik
    if deadline_date is None:
        return True

    return deadline_date < MIN_DEADLINE_DATE


def is_blocked_status(tender):
    status = tender.get("status")

    if not status:
        return False

    status = str(status).lower().strip()

    blocked_words = [
        "отменён",
        "отменен",
        "отменена",
        "отменено",
        "отменённый",
        "отмененный",
        "завершён",
        "завершен",
        "завершена",
        "завершено"
    ]

    return any(word in status for word in blocked_words)


def is_blocked_tender_type(tender):
    """
    44-ФЗ və 223-ФЗ tipli tenderləri bütün source-lar üçün bloklayır.
    """

    tender_type = get_tender_type(tender)

    if not tender_type:
        return False

    tender_type = str(tender_type).lower().strip()

    blocked_patterns = [
        "44-фз",
        "44 фз",
        "44fz",
        "44-fz",
        "№ 44-фз",
        "223-фз",
        "223 фз",
        "223fz",
        "223-fz",
        "№ 223-фз",
    ]

    return any(pattern in tender_type for pattern in blocked_patterns)


def get_rub_to_azn_rate():
    """
    CBAR tarixli XML-dən RUB -> AZN məzənnəsini götürür.
    Əgər bu gün üçün XML açılmasa, son 10 günə baxır.
    """

    for day_offset in range(0, 10):
        target_date = date.today() - timedelta(days=day_offset)
        date_text = target_date.strftime("%d.%m.%Y")

        url = f"https://www.cbar.az/currencies/{date_text}.xml"

        try:
            response = requests.get(
                url,
                timeout=20,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/148.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/xml,text/xml,*/*"
                }
            )

            if response.status_code != 200:
                print(f"[RATE SKIP] CBAR status {response.status_code}: {url}")
                continue

            content = response.content.strip()

            if not content.startswith(b"<?xml") and not content.startswith(b"<ValCurs"):
                print(f"[RATE SKIP] CBAR XML deyil: {url}")
                continue

            root = ET.fromstring(content)

            for val_type in root.findall(".//ValType"):
                for valute in val_type.findall("Valute"):
                    code = valute.attrib.get("Code")

                    if code == "RUB":
                        nominal_text = valute.findtext("Nominal", default="1")
                        value_text = valute.findtext("Value", default="0")

                        nominal = float(nominal_text.replace(",", "."))
                        value = float(value_text.replace(",", "."))

                        if nominal <= 0 or value <= 0:
                            raise ValueError("RUB məzənnəsi düzgün oxunmadı")

                        rate = value / nominal

                        print("CBAR məzənnə tarixi:", date_text)
                        print("CBAR RUB nominal:", nominal)
                        print("CBAR RUB value:", value)
                        print("1 RUB =", rate, "AZN")

                        return rate

            print(f"[RATE SKIP] RUB tapılmadı: {url}")

        except Exception as e:
            print(f"[RATE ERROR] {url} | {e}")
            continue

    print("[RATE ERROR] Son 10 gün üçün RUB -> AZN məzənnəsi tapılmadı.")
    return None


def parse_price_to_number(price_text):
    if not price_text:
        return 0

    text = str(price_text).lower()

    no_price_words = [
        "сумма не задана",
        "не задана",
        "не указана",
        "yoxdur",
        "qiymət yoxdur",
        "none",
        "-"
    ]

    if any(word in text for word in no_price_words):
        return 0

    text = text.replace("\xa0", " ")
    text = text.replace("₽", "")
    text = text.replace("руб.", "")
    text = text.replace("руб", "")
    text = text.replace("рублей", "")
    text = text.replace("ruble", "")
    text = text.replace("rub", "")
    text = text.replace("AZN", "")
    text = text.replace("azn", "")
    text = text.replace("₼", "")
    text = text.strip()

    match = re.search(r"[\d\s]+(?:[,.]\d{1,2})?", text)

    if not match:
        return 0

    number_text = match.group(0)

    number_text = number_text.replace(" ", "")
    number_text = number_text.replace(",", ".")

    try:
        return float(number_text)
    except Exception:
        return 0


def format_number(value):
    try:
        return f"{value:,.2f}".replace(",", " ")
    except Exception:
        return str(value)


def format_price_with_azn(price_text, rub_to_azn_rate):
    price_number = parse_price_to_number(price_text)

    if price_number <= 0:
        return clean_value(price_text, "Qiymət yoxdur")

    rub_text = f"{format_number(price_number)} ₽"

    if rub_to_azn_rate is None:
        return rub_text

    azn_value = price_number * rub_to_azn_rate
    azn_text = f"{round(azn_value)} AZN"

    return f"{rub_text} ({azn_text})"


def is_price_below_minimum(tender):
    price_text = tender.get("price")
    price_number = parse_price_to_number(price_text)

    # Qiymət tapılmırsa, göndərmirik
    if price_number <= 0:
        return True

    return price_number < MIN_PRICE_RUB


def get_title_icon(price_text):
    price_number = parse_price_to_number(price_text)

    if price_number > 5_000_000:
        return "🔥"

    return "✅"


def load_keywords():
    with open("keywords.txt", "r", encoding="utf-8") as file:
        keywords = []

        for line in file:
            keyword = line.strip()

            if keyword:
                keywords.append(keyword)

        return keywords


def make_title_clickable(title, title_links=None):
    title = clean_value(title, "Başlıq yoxdur")
    escaped_title = html.escape(title)

    if not title_links:
        return escaped_title

    for item in title_links:
        text = item.get("text")
        url = item.get("url")

        if not text or not url:
            continue

        escaped_text = html.escape(str(text))
        escaped_url = html.escape(str(url), quote=True)

        escaped_title = escaped_title.replace(
            escaped_text,
            f'<a href="{escaped_url}">{escaped_text}</a>'
        )

    return escaped_title


def get_tender_type(tender):
    return (
        tender.get("tender_type")
        or tender.get("purchase_type")
        or tender.get("type")
    )


def get_deadline(tender):
    return (
        tender.get("deadline")
        or tender.get("application_end")
    )


def get_publish_date(tender):
    return (
        tender.get("publish_date")
        or tender.get("published_at")
        or tender.get("date")
    )


def normalize_hash_text(value):
    """
    Tender title üçün normalizasiya.
    """

    if value is None:
        return ""

    value = str(value).lower().strip()

    replacements = {
        "«": " ",
        "»": " ",
        '"': " ",
        "“": " ",
        "”": " ",
        "„": " ",
        "–": " ",
        "—": " ",
        "-": " ",
        "№": " ",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    value = re.sub(r"[^a-zа-яё0-9]+", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip()

    return value


def make_tender_content_hash(tender):
    """
    Eyni tender fərqli source-lardan gəlsə belə təkrar göndərilməsin deyə
    yalnız əsas sabit məlumatlardan hash yaradırıq.

    Əsas prinsip:
    normalized_title + price
    """

    title = normalize_hash_text(tender.get("title"))

    price_number = parse_price_to_number(tender.get("price"))
    price = str(int(price_number)) if price_number > 0 else ""

    if not title or not price:
        return ""

    raw_text = "|".join([
        title,
        price
    ])

    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def build_telegram_message(tender, rub_to_azn_rate):
    translated_title = tender.get("translated_title")

    title = translated_title or tender.get("title")

    # Əgər title AI ilə tərcümə olunubsa, əvvəlki title_links artıq rus mətninə aid olacaq.
    # Ona görə tərcümə olunmuş başlıqda clickable title tətbiq etmirik.
    title_links = [] if translated_title else tender.get("title_links", [])

    organization = clean_value(
        tender.get("translated_organization")
        or tender.get("organization")
        or tender.get("customer")
        or tender.get("company"),
        "Təşkilat yoxdur"
    )

    price = format_price_with_azn(tender.get("price"), rub_to_azn_rate)

    tender_type = clean_value(
        tender.get("translated_tender_type")
        or get_tender_type(tender),
        "Tip yoxdur"
    )

    status = clean_value(
        tender.get("translated_status")
        or tender.get("status"),
        "Status yoxdur"
    )

    deadline = clean_value(
        tender.get("translated_deadline")
        or get_deadline(tender),
        "Son tarix yoxdur"
    )

    publish_date = clean_value(
        tender.get("translated_publish_date")
        or get_publish_date(tender),
        "Paylaşılma tarixi yoxdur"
    )

    tender_url = clean_value(tender.get("url"), "Link yoxdur")

    title_icon = get_title_icon(tender.get("price"))
    clickable_title = make_title_clickable(title, title_links)

    message = f"""{title_icon} <b>{clickable_title}</b>
 - 🏫 <b>"{html.escape(organization)}"</b>

 - 💰Qiymət : <b>{html.escape(price)}</b>
 - 🧾Tip : <b>{html.escape(tender_type)}</b>
 - 📌Status : <b>{html.escape(status)}</b>
 - ⏰Son tarix : <b>{html.escape(deadline)}</b>
 - 📅Paylaşılma tarixi : <b>{html.escape(publish_date)}</b>
 - 🔗Link : <b>{html.escape(tender_url)}</b>"""

    tender["translated_message"] = message

    return message


def send_to_telegram(tender, rub_to_azn_rate):
    message = build_telegram_message(tender, rub_to_azn_rate)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHANNEL_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        },
        timeout=30
    )

    print("Telegram status:", response.status_code)
    print(response.text)

    return response.status_code == 200


def create_page(context):
    page = context.new_page()

    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        })
    """)

    page.set_default_timeout(60000)
    page.set_default_navigation_timeout(60000)

    return page


def normalize_tender(tender, source_name, keyword):
    tender["source"] = tender.get("source") or source_name
    tender["keyword"] = tender.get("keyword") or keyword

    tender["title"] = tender.get("title") or ""
    tender["url"] = tender.get("url") or ""

    tender["organization"] = (
        tender.get("organization")
        or tender.get("customer")
        or tender.get("company")
    )

    tender["tender_type"] = (
        tender.get("tender_type")
        or tender.get("purchase_type")
        or tender.get("type")
    )

    tender["deadline"] = (
        tender.get("deadline")
        or tender.get("application_end")
    )

    tender["publish_date"] = (
        tender.get("publish_date")
        or tender.get("published_at")
        or tender.get("date")
    )

    if "title_links" not in tender or tender["title_links"] is None:
        tender["title_links"] = []

    return tender


def main():
    init_db()

    keywords = load_keywords()

    rub_to_azn_rate = get_rub_to_azn_rate()

    print("Minimum paylaşılma tarixi:", MIN_PUBLISH_DATE.strftime("%d.%m.%Y"))
    print("Minimum son tarix:", MIN_DEADLINE_DATE.strftime("%d.%m.%Y"))
    print("Minimum qiymət:", MIN_PRICE_RUB, "RUB")

    if rub_to_azn_rate is None:
        print("RUB -> AZN məzənnəsi tapılmadı. Telegram-da yalnız RUB göstəriləcək.")
    else:
        print("RUB -> AZN rate:", rub_to_azn_rate)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-http2",
                "--ignore-certificate-errors",
            ]
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1536, "height": 864},
            locale="ru-RU",
            ignore_https_errors=True,
        )

        print("Active sources:", [source["name"] for source in ACTIVE_SOURCES])

        for keyword in keywords:
            print("===================================")
            print("Keyword:", keyword)

            for source in ACTIVE_SOURCES:
                source_name = source["name"]
                search_func = source["search_func"]

                print("Source:", source_name)

                page = create_page(context)

                try:
                    tenders = search_func(page, keyword)
                except Exception as e:
                    print(f"[SOURCE ERROR] {source_name} | Keyword: {keyword} | {e}")
                    tenders = []
                finally:
                    try:
                        page.close()
                    except Exception:
                        pass

                print("Tender count:", len(tenders))

                sent_count = 0

                for tender in tenders:
                    tender = normalize_tender(tender, source_name, keyword)

                    if not tender.get("url"):
                        print("Keçildi, URL yoxdur")
                        continue

                    if tender_exists(tender_url=tender["url"]):
                        print("Keçildi, artıq göndərilib URL üzrə:", tender["url"])
                        continue

                    print("Detail parser işləyir:")
                    print(tender["title"])
                    print(tender["url"])

                    detail_page = create_page(context)

                    try:
                        tender = parse_tender_detail(detail_page, tender)
                        tender = normalize_tender(tender, source_name, keyword)
                    except Exception as e:
                        print(f"[DETAIL ERROR] {tender['url']} | {e}")
                    finally:
                        try:
                            detail_page.close()
                        except Exception:
                            pass

                    tender["content_hash"] = make_tender_content_hash(tender)

                    if tender_exists(content_hash=tender["content_hash"]):
                        print("Keçildi, artıq göndərilib content üzrə:")
                        print(tender["title"])
                        print(tender["url"])
                        print("Content hash:", tender["content_hash"])
                        continue

                    # Hazırda publish date filter söndürülüb.
                    # Lazım olsa, aşağıdakı hissəni aktiv edə bilərsən.
                    # if is_old_publish_date(tender):
                    #     print("Keçildi, paylaşılma tarixi köhnədir və ya tapılmadı:")
                    #     print(tender["title"])
                    #     print(tender["url"])
                    #     print("Paylaşılma tarixi:", get_publish_date(tender))
                    #     print("Minimum tarix:", MIN_PUBLISH_DATE.strftime("%d.%m.%Y"))
                    #     continue

                    if is_deadline_too_close_or_missing(tender):
                        print("Keçildi, son müraciət tarixi yaxındır və ya tapılmadı:")
                        print(tender["title"])
                        print(tender["url"])
                        print("Son tarix:", get_deadline(tender))
                        print("Minimum son tarix:", MIN_DEADLINE_DATE.strftime("%d.%m.%Y"))
                        continue

                    if is_blocked_status(tender):
                        print("Keçildi, tender statusu uyğun deyil:")
                        print(tender["title"])
                        print(tender["url"])
                        print("Status:", tender.get("status"))
                        continue

                    if is_blocked_tender_type(tender):
                        print("Keçildi, tender tipi bloklanıb:")
                        print(tender["title"])
                        print(tender["url"])
                        print("Tip:", get_tender_type(tender))
                        continue

                    if is_price_below_minimum(tender):
                        print("Keçildi, qiymət 450k RUB-dan aşağıdır və ya qiymət tapılmadı:")
                        print(tender["title"])
                        print(tender["url"])
                        print("Qiymət:", tender.get("price"))
                        print("Oxunan qiymət:", parse_price_to_number(tender.get("price")))
                        print("Minimum qiymət:", MIN_PRICE_RUB)
                        continue

                    print("AI tərcümə işləyir:")
                    tender = translate_tender_to_az(tender)

                    print("Telegram-a göndərilir:")
                    print(tender.get("translated_title") or tender.get("title"))
                    print(tender["url"])
                    print("Qiymət:", tender.get("price"))
                    print("Oxunan qiymət:", parse_price_to_number(tender.get("price")))
                    print("Content hash:", tender.get("content_hash"))

                    if rub_to_azn_rate is not None:
                        print(
                            "AZN ekvivalenti:",
                            parse_price_to_number(tender.get("price")) * rub_to_azn_rate
                        )

                    sent = send_to_telegram(tender, rub_to_azn_rate)

                    if sent:
                        print("DB-yə yazılacaq tender məlumatları:")
                        print("URL:", tender.get("url"))
                        print("Title:", tender.get("title"))
                        print("Translated title:", tender.get("translated_title"))
                        print("Price:", tender.get("price"))
                        print("Deadline:", get_deadline(tender))
                        print("Translated deadline:", tender.get("translated_deadline"))
                        print("Publish date:", get_publish_date(tender))
                        print("Translated publish date:", tender.get("translated_publish_date"))
                        print("Tender type:", get_tender_type(tender))
                        print("Translated tender type:", tender.get("translated_tender_type"))
                        print("Status:", tender.get("status"))
                        print("Translated status:", tender.get("translated_status"))
                        print("Tender ID:", tender.get("tender_id"))

                        save_tender(tender)
                        sent_count += 1

                    if sent_count >= MAX_SEND_PER_KEYWORD:
                        print(f"Limit doldu: {source_name} / {keyword}")
                        break

                    time.sleep(2)

                if sent_count == 0:
                    print("Yeni tender yoxdur")

                time.sleep(3)

        browser.close()


if __name__ == "__main__":
    main()
