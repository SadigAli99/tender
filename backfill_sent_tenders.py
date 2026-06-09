import re
import sqlite3
import hashlib
from datetime import datetime

from playwright.sync_api import sync_playwright

from detail_parser import parse_tender_detail


DB_NAME = "tenders.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def normalize_title(title: str) -> str:
    if not title:
        return ""

    title = str(title).lower()

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
        title = title.replace(old, new)

    title = re.sub(r"[^a-zа-яё0-9]+", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip()

    return title


def normalize_price(price) -> str:
    if price is None:
        return ""

    price = str(price)

    no_price_words = [
        "сумма не задана",
        "не задана",
        "не указана",
        "yoxdur",
        "qiymət yoxdur",
        "none",
        "-"
    ]

    if any(word in price.lower() for word in no_price_words):
        return ""

    price = price.replace("₽", "")
    price = price.replace("руб.", "")
    price = price.replace("руб", "")
    price = price.replace("Руб.", "")
    price = price.replace("Руб", "")
    price = price.replace("рублей", "")
    price = price.replace("RUB", "")
    price = price.replace("rub", "")
    price = price.replace("AZN", "")
    price = price.replace("azn", "")
    price = price.replace("₼", "")
    price = price.replace("\xa0", "")
    price = price.replace(" ", "")
    price = price.replace(",", ".")

    match = re.search(r"\d+(?:\.\d+)?", price)

    if not match:
        return ""

    try:
        return str(int(float(match.group(0))))
    except Exception:
        return ""


def parse_date_for_db(value):
    if not value:
        return None

    text = str(value).strip()

    match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)

    if not match:
        return None

    day, month, year = match.groups()

    try:
        parsed_date = datetime(int(year), int(month), int(day))
        return parsed_date.strftime("%Y-%m-%d")
    except Exception:
        return None


def make_title_hash(title: str) -> str:
    normalized = normalize_title(title)

    if not normalized:
        return ""

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def make_content_hash(title: str, price) -> str:
    normalized = normalize_title(title)
    price_rub = normalize_price(price)

    if not normalized or not price_rub:
        return ""

    raw = f"{normalized}|{price_rub}"

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_source_from_url(url):
    if not url:
        return ""

    if "win.myseldon.com" in url:
        return "win.myseldon.com"

    if "rostender.info" in url:
        return "rostender.info"

    if "zakupki.kontur.ru" in url:
        return "zakupki.kontur.ru"

    return ""


def extract_tender_id_from_url(url):
    if not url:
        return None

    url = str(url)

    # Seldon:
    # https://win.myseldon.com/tender/card/gos/42821838/main?uuid=...
    match = re.search(r"/tender/card/[^/]+/(\d+)/", url)
    if match:
        return match.group(1)

    # Rostender:
    # https://rostender.info/.../92942735-tender-...
    match = re.search(r"/(\d+)-tender-", url)
    if match:
        return match.group(1)

    # Rostender qısa link:
    # https://rostender.info/tender/92889026
    match = re.search(r"/tender/(\d+)", url)
    if match:
        return match.group(1)

    # Kontur:
    # https://zakupki.kontur.ru/IS59732887
    # https://zakupki.kontur.ru/0873400004326000011
    match = re.search(r"zakupki\.kontur\.ru/([^/?#]+)", url)
    if match:
        return match.group(1)

    return None


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


def ensure_columns():
    connection = get_connection()
    cursor = connection.cursor()

    columns = [
        ("price_text", "TEXT"),
        ("price_rub", "TEXT"),
        ("deadline_text", "TEXT"),
        ("deadline_date", "TEXT"),
        ("publish_date_text", "TEXT"),
        ("publish_date", "TEXT"),
        ("tender_type", "TEXT"),
        ("status", "TEXT"),
        ("tender_id", "TEXT"),
        ("title_hash", "TEXT"),
        ("content_hash", "TEXT"),
        ("normalized_title", "TEXT"),
    ]

    cursor.execute("PRAGMA table_info(sent_tenders)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    for column_name, column_type in columns:
        if column_name not in existing_columns:
            print("Column added:", column_name)
            cursor.execute(
                f"ALTER TABLE sent_tenders ADD COLUMN {column_name} {column_type}"
            )

    connection.commit()
    connection.close()


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


def load_existing_rows():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            tender_url,
            title,
            keyword,
            source,
            price_rub
        FROM sent_tenders
        ORDER BY id ASC
    """)

    rows = cursor.fetchall()

    connection.close()

    return rows


def content_hash_exists_for_other_row(cursor, content_hash, row_id):
    if not content_hash:
        return False

    cursor.execute("""
        SELECT id
        FROM sent_tenders
        WHERE content_hash = ?
          AND id != ?
        LIMIT 1
    """, (
        content_hash,
        row_id
    ))

    return cursor.fetchone() is not None


def update_row(row_id, tender):
    connection = get_connection()
    cursor = connection.cursor()

    title = tender.get("title") or ""
    price_text = tender.get("price") or ""
    price_rub = normalize_price(price_text)

    old_price_rub = tender.get("old_price_rub")
    if not price_rub and old_price_rub:
        price_rub = str(old_price_rub)

    deadline_text = get_deadline(tender)
    deadline_date = parse_date_for_db(deadline_text)

    publish_date_text = get_publish_date(tender)
    publish_date = parse_date_for_db(publish_date_text)

    tender_type = get_tender_type(tender)
    status = tender.get("status")

    tender_id = tender.get("tender_id") or extract_tender_id_from_url(tender.get("url"))

    normalized_title = normalize_title(title)
    title_hash = make_title_hash(title)

    content_hash = tender.get("content_hash")
    if not content_hash:
        content_hash = make_content_hash(title, price_text or price_rub)

    if content_hash_exists_for_other_row(cursor, content_hash, row_id):
        print("Content hash başqa tenderdə var, content_hash update edilmir:", content_hash)
        content_hash_to_update = None
    else:
        content_hash_to_update = content_hash

    cursor.execute("""
        UPDATE sent_tenders
        SET
            title = COALESCE(NULLIF(?, ''), title),
            source = COALESCE(NULLIF(?, ''), source),
            price_text = ?,
            price_rub = ?,
            deadline_text = ?,
            deadline_date = ?,
            publish_date_text = ?,
            publish_date = ?,
            tender_type = ?,
            status = ?,
            tender_id = ?,
            title_hash = ?,
            normalized_title = ?
        WHERE id = ?
    """, (
        title,
        tender.get("source") or "",
        price_text,
        price_rub,
        deadline_text,
        deadline_date,
        publish_date_text,
        publish_date,
        tender_type,
        status,
        tender_id,
        title_hash,
        normalized_title,
        row_id
    ))

    if content_hash_to_update:
        cursor.execute("""
            UPDATE sent_tenders
            SET content_hash = ?
            WHERE id = ?
        """, (
            content_hash_to_update,
            row_id
        ))

    connection.commit()
    connection.close()


def main():
    ensure_columns()

    rows = load_existing_rows()

    print("Update ediləcək tender sayı:", len(rows))

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

        for index, row in enumerate(rows, start=1):
            row_id, tender_url, title, keyword, source, old_price_rub = row

            print("=" * 80)
            print(f"{index}/{len(rows)} | ID: {row_id}")
            print("URL:", tender_url)

            tender = {
                "url": tender_url,
                "title": title or "",
                "keyword": keyword or "",
                "source": source or get_source_from_url(tender_url),
                "old_price_rub": old_price_rub,
                "tender_id": extract_tender_id_from_url(tender_url),
            }

            page = create_page(context)

            try:
                tender = parse_tender_detail(page, tender)
            except Exception as e:
                print("[DETAIL ERROR]", e)
            finally:
                try:
                    page.close()
                except Exception:
                    pass

            if not tender.get("source"):
                tender["source"] = get_source_from_url(tender_url)

            if not tender.get("tender_id"):
                tender["tender_id"] = extract_tender_id_from_url(tender_url)

            print("Title:", tender.get("title"))
            print("Price:", tender.get("price"))
            print("Deadline:", get_deadline(tender))
            print("Publish date:", get_publish_date(tender))
            print("Tender type:", get_tender_type(tender))
            print("Status:", tender.get("status"))
            print("Tender ID:", tender.get("tender_id"))

            try:
                update_row(row_id, tender)
                print("DB updated.")
            except Exception as e:
                print("[DB UPDATE ERROR]", e)
                print("Bu sətr keçildi:", row_id)
                continue

        browser.close()

    print("Backfill tamamlandı.")


if __name__ == "__main__":
    main()
