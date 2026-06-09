import sqlite3
import hashlib
import re
from datetime import datetime


DB_NAME = "tenders.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()

    for column in columns:
        if column[1] == column_name:
            return True

    return False


def add_column_if_missing(cursor, table_name, column_name, column_type):
    if not column_exists(cursor, table_name, column_name):
        cursor.execute(f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {column_type}
        """)


def normalize_title(title: str) -> str:
    """
    Tender başlığını source-lar arasında müqayisə üçün standart formaya salır.
    Məsələn:
    «Личный кабинет» və Личный кабинет eyni qəbul olunacaq.
    """
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
    """
    Qiyməti standart tam ədəd formaya salır.
    Məsələn:
    4 636 000.00 ₽ -> 4636000
    4 636 000,00 -> 4636000
    """
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


def parse_price_to_float(price):
    normalized_price = normalize_price(price)

    if not normalized_price:
        return None

    try:
        return float(normalized_price)
    except Exception:
        return None


def parse_date_for_db(value):
    """
    DD.MM.YYYY və DD.MM.YYYY HH:MM formatını DB üçün YYYY-MM-DD formatına çevirir.

    Məsələn:
    16.06.2026 10:00 -> 2026-06-16
    08.06.2026 -> 2026-06-08
    """
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


def make_content_hash(title: str, price) -> str:
    """
    Eyni tenderi fərqli source-lardan tanımaq üçün hash yaradır.
    Əsas prinsip:
    normalized_title + normalized_price
    """
    normalized_title = normalize_title(title)
    normalized_price = normalize_price(price)

    if not normalized_title or not normalized_price:
        return ""

    raw_value = f"{normalized_title}|{normalized_price}"

    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


def make_title_hash(title: str) -> str:
    normalized_title = normalize_title(title)

    if not normalized_title:
        return ""

    return hashlib.sha256(normalized_title.encode("utf-8")).hexdigest()


def get_tender_type_for_db(tender):
    return (
        tender.get("tender_type")
        or tender.get("purchase_type")
        or tender.get("type")
    )


def get_deadline_for_db(tender):
    return (
        tender.get("deadline")
        or tender.get("application_end")
    )


def get_publish_date_for_db(tender):
    return (
        tender.get("publish_date")
        or tender.get("published_at")
        or tender.get("date")
    )


def init_db():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sent_tenders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_url TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            keyword TEXT NOT NULL,
            source TEXT,
            content_hash TEXT,
            normalized_title TEXT,
            price_rub TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    add_column_if_missing(cursor, "sent_tenders", "source", "TEXT")
    add_column_if_missing(cursor, "sent_tenders", "content_hash", "TEXT")
    add_column_if_missing(cursor, "sent_tenders", "normalized_title", "TEXT")
    add_column_if_missing(cursor, "sent_tenders", "price_rub", "TEXT")

    add_column_if_missing(cursor, "sent_tenders", "price_text", "TEXT")
    add_column_if_missing(cursor, "sent_tenders", "deadline_text", "TEXT")
    add_column_if_missing(cursor, "sent_tenders", "deadline_date", "TEXT")
    add_column_if_missing(cursor, "sent_tenders", "publish_date_text", "TEXT")
    add_column_if_missing(cursor, "sent_tenders", "publish_date", "TEXT")
    add_column_if_missing(cursor, "sent_tenders", "tender_type", "TEXT")
    add_column_if_missing(cursor, "sent_tenders", "status", "TEXT")
    add_column_if_missing(cursor, "sent_tenders", "tender_id", "TEXT")
    add_column_if_missing(cursor, "sent_tenders", "title_hash", "TEXT")

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_sent_tenders_content_hash
        ON sent_tenders(content_hash)
        WHERE content_hash IS NOT NULL AND content_hash != ''
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sent_tenders_tender_id
        ON sent_tenders(tender_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sent_tenders_tender_type
        ON sent_tenders(tender_type)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sent_tenders_deadline_date
        ON sent_tenders(deadline_date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sent_tenders_publish_date
        ON sent_tenders(publish_date)
    """)

    connection.commit()
    connection.close()


def tender_exists(tender_url=None, content_hash=None):
    if not tender_url and not content_hash:
        return True

    connection = get_connection()
    cursor = connection.cursor()

    if content_hash:
        cursor.execute(
            "SELECT id FROM sent_tenders WHERE content_hash = ? LIMIT 1",
            (content_hash,)
        )

        result = cursor.fetchone()

        if result is not None:
            connection.close()
            return True

    if tender_url:
        cursor.execute(
            "SELECT id FROM sent_tenders WHERE tender_url = ? LIMIT 1",
            (tender_url,)
        )

        result = cursor.fetchone()

        if result is not None:
            connection.close()
            return True

    connection.close()
    return False


def save_tender(tender):
    connection = get_connection()
    cursor = connection.cursor()

    title = tender.get("title", "")
    price_text = tender.get("price", "")

    normalized_title = normalize_title(title)
    price_rub = normalize_price(price_text)

    content_hash = tender.get("content_hash", "")

    if not content_hash:
        content_hash = make_content_hash(title, price_text)

    title_hash = tender.get("title_hash", "")

    if not title_hash:
        title_hash = make_title_hash(title)

    deadline_text = get_deadline_for_db(tender)
    deadline_date = parse_date_for_db(deadline_text)

    publish_date_text = get_publish_date_for_db(tender)
    publish_date = parse_date_for_db(publish_date_text)

    tender_type = get_tender_type_for_db(tender)
    status = tender.get("status")

    tender_id = tender.get("tender_id")

    cursor.execute("""
        INSERT OR IGNORE INTO sent_tenders (
            tender_url,
            title,
            keyword,
            source,
            content_hash,
            normalized_title,
            price_rub,
            price_text,
            deadline_text,
            deadline_date,
            publish_date_text,
            publish_date,
            tender_type,
            status,
            tender_id,
            title_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        tender.get("url", ""),
        title,
        tender.get("keyword", ""),
        tender.get("source", ""),
        content_hash,
        normalized_title,
        price_rub,
        price_text,
        deadline_text,
        deadline_date,
        publish_date_text,
        publish_date,
        tender_type,
        status,
        tender_id,
        title_hash
    ))

    cursor.execute("""
        UPDATE sent_tenders
        SET
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
            normalized_title = ?,
            content_hash = ?
        WHERE tender_url = ?
    """, (
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
        content_hash,
        tender.get("url", "")
    ))

    connection.commit()
    connection.close()

    connection.commit()
    connection.close()
