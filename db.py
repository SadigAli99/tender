import sqlite3

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

    if tender_url:
        cursor.execute(
            "SELECT id FROM sent_tenders WHERE tender_url = ? LIMIT 1",
            (tender_url,)
        )

        result = cursor.fetchone()

        if result is not None:
            connection.close()
            return True

    if content_hash:
        cursor.execute(
            "SELECT id FROM sent_tenders WHERE content_hash = ? LIMIT 1",
            (content_hash,)
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

    cursor.execute("""
        INSERT OR IGNORE INTO sent_tenders (
            tender_url,
            title,
            keyword,
            source,
            content_hash
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        tender.get("url", ""),
        tender.get("title", ""),
        tender.get("keyword", ""),
        tender.get("source", ""),
        tender.get("content_hash", "")
    ))

    connection.commit()
    connection.close()
