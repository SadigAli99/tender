import sqlite3
import hashlib
import re

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

    # Hərf və rəqəmdən başqa simvolları boşluğa çeviririk
    title = re.sub(r"[^a-zа-яё0-9]+", " ", title, flags=re.IGNORECASE)

    # Artıq boşluqları təmizləyirik
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

    price = price.replace("₽", "")
    price = price.replace("руб.", "")
    price = price.replace("руб", "")
    price = price.replace("Руб.", "")
    price = price.replace("Руб", "")
    price = price.replace("\xa0", "")
    price = price.replace(" ", "")
    price = price.replace(",", ".")

    match = re.search(r"\d+(?:\.\d+)?", price)

    if not match:
        return ""

    return str(int(float(match.group(0))))


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

    if not column_exists(cursor, "sent_tenders", "source"):
        cursor.execute("""
            ALTER TABLE sent_tenders
            ADD COLUMN source TEXT
        """)

    if not column_exists(cursor, "sent_tenders", "content_hash"):
        cursor.execute("""
            ALTER TABLE sent_tenders
            ADD COLUMN content_hash TEXT
        """)

    if not column_exists(cursor, "sent_tenders", "normalized_title"):
        cursor.execute("""
            ALTER TABLE sent_tenders
            ADD COLUMN normalized_title TEXT
        """)

    if not column_exists(cursor, "sent_tenders", "price_rub"):
        cursor.execute("""
            ALTER TABLE sent_tenders
            ADD COLUMN price_rub TEXT
        """)

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_sent_tenders_content_hash
        ON sent_tenders(content_hash)
        WHERE content_hash IS NOT NULL AND content_hash != ''
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
    price = tender.get("price", "")

    normalized_title = normalize_title(title)
    price_rub = normalize_price(price)

    content_hash = tender.get("content_hash", "")

    if not content_hash:
        content_hash = make_content_hash(title, price)

    cursor.execute("""
        INSERT OR IGNORE INTO sent_tenders (
            tender_url,
            title,
            keyword,
            source,
            content_hash,
            normalized_title,
            price_rub
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        tender.get("url", ""),
        title,
        tender.get("keyword", ""),
        tender.get("source", ""),
        content_hash,
        normalized_title,
        price_rub
    ))

    connection.commit()
    connection.close()
