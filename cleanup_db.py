import sqlite3

from playwright.sync_api import sync_playwright

from db import init_db
from detail_parser import parse_tender_detail

from search import (
    create_page,
    normalize_tender,
    is_old_publish_date,
    is_deadline_too_close_or_missing,
    is_blocked_status,
    is_price_below_minimum,
    get_publish_date,
    get_deadline,
    parse_price_to_number,
    make_tender_content_hash,
    MIN_PUBLISH_DATE,
    MIN_DEADLINE_DATE,
    MIN_PRICE_RUB,
)


DB_NAME = "tenders.db"


def get_all_tenders_from_db():
    connection = sqlite3.connect(DB_NAME)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            tender_url,
            title,
            keyword,
            source,
            content_hash
        FROM sent_tenders
        WHERE tender_url IS NOT NULL
          AND tender_url != ''
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()
    connection.close()

    tenders = []

    for row in rows:
        tenders.append({
            "id": row["id"],
            "url": row["tender_url"],
            "title": row["title"],
            "keyword": row["keyword"],
            "source": row["source"],
            "content_hash": row["content_hash"],
        })

    return tenders


def delete_tender_from_db(tender_id):
    connection = sqlite3.connect(DB_NAME)
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM sent_tenders WHERE id = ?",
        (tender_id,)
    )

    connection.commit()
    connection.close()


def should_delete_tender(tender):
    if is_old_publish_date(tender):
        return True, "paylaşılma tarixi köhnədir və ya tapılmadı"

    if is_deadline_too_close_or_missing(tender):
        return True, "son müraciət tarixi yaxındır və ya tapılmadı"

    if is_blocked_status(tender):
        return True, "status uyğun deyil"

    if is_price_below_minimum(tender):
        return True, "qiymət 450k RUB-dan aşağıdır və ya tapılmadı"

    return False, ""


def cleanup_db():
    init_db()

    tenders = get_all_tenders_from_db()

    print("Bazadakı tender sayı:", len(tenders))
    print("Minimum paylaşılma tarixi:", MIN_PUBLISH_DATE.strftime("%d.%m.%Y"))
    print("Minimum son tarix:", MIN_DEADLINE_DATE.strftime("%d.%m.%Y"))
    print("Minimum qiymət:", MIN_PRICE_RUB, "RUB")

    deleted_count = 0
    kept_count = 0
    error_count = 0

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

        try:
            for index, tender in enumerate(tenders, start=1):
                tender_id = tender["id"]
                source_name = tender.get("source")
                keyword = tender.get("keyword") or "CLEANUP"

                print("\n===================================")
                print(f"Yoxlanılır: {index}/{len(tenders)}")
                print("ID:", tender_id)
                print("Title:", tender.get("title"))
                print("URL:", tender.get("url"))
                print("Source:", source_name)

                detail_page = create_page(context)

                try:
                    tender = normalize_tender(tender, source_name, keyword)

                    tender = parse_tender_detail(detail_page, tender)
                    tender = normalize_tender(tender, source_name, keyword)

                    tender["content_hash"] = make_tender_content_hash(tender)

                    print("Parser-dən sonra:")
                    print("Status:", tender.get("status"))
                    print("Publish date:", get_publish_date(tender))
                    print("Deadline:", get_deadline(tender))
                    print("Price:", tender.get("price"))
                    print("Oxunan qiymət:", parse_price_to_number(tender.get("price")))

                    should_delete, reason = should_delete_tender(tender)

                    if should_delete:
                        delete_tender_from_db(tender_id)
                        deleted_count += 1

                        print("SİLİNDİ:", reason)
                        continue

                    kept_count += 1
                    print("Saxlanıldı: şərtlərə uyğundur")

                except Exception as e:
                    error_count += 1
                    print("[CLEANUP ERROR]", tender.get("url"), "|", e)

                finally:
                    try:
                        detail_page.close()
                    except Exception:
                        pass

        finally:
            browser.close()

    print("\n========== NƏTİCƏ ==========")
    print("Ümumi yoxlanılan:", len(tenders))
    print("Silinən:", deleted_count)
    print("Saxlanılan:", kept_count)
    print("Xəta olan:", error_count)


if __name__ == "__main__":
    cleanup_db()
