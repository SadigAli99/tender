import sqlite3

from playwright.sync_api import sync_playwright

from db import init_db
from detail_parser import parse_tender_detail

from search import (
    get_rub_to_azn_rate,
    create_page,
    normalize_tender,
    is_old_publish_date,
    is_price_below_minimum,
    get_publish_date,
    parse_price_to_number,
    send_to_telegram,
    make_tender_content_hash,
    MIN_PUBLISH_DATE,
    MIN_PRICE_RUB,
)


DB_NAME = "tenders.db"


def get_tenders_from_db(limit=50):
    connection = sqlite3.connect(DB_NAME)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            tender_url,
            title,
            keyword,
            source,
            content_hash
        FROM sent_tenders
        WHERE tender_url IS NOT NULL
          AND tender_url != ''
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    connection.close()

    tenders = []

    for row in rows:
        tender = {
            "url": row["tender_url"],
            "title": row["title"],
            "keyword": row["keyword"],
            "source": row["source"],
            "content_hash": row["content_hash"],
        }

        if tender.get("url") and tender.get("source"):
            tenders.append(tender)

    return tenders


def send_first_valid_test_tender():
    init_db()

    tenders = get_tenders_from_db(limit=100)

    if not tenders:
        print("Bazadan test üçün tender tapılmadı.")
        return

    print("Bazadan götürülən tender sayı:", len(tenders))

    rub_to_azn_rate = get_rub_to_azn_rate()

    if rub_to_azn_rate is None:
        print("RUB -> AZN məzənnəsi tapılmadı. Test göndərişi dayandırıldı.")
        return

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

        try:
            for index, tender in enumerate(tenders, start=1):
                source_name = tender.get("source")
                keyword = tender.get("keyword") or "TEST"

                print("\n===================================")
                print(f"Test edilir: {index}/{len(tenders)}")
                print("Title:", tender.get("title"))
                print("URL:", tender.get("url"))
                print("Source:", source_name)
                print("Keyword:", keyword)

                detail_page = create_page(context)

                try:
                    tender = normalize_tender(tender, source_name, keyword)

                    print("Detail parser işləyir...")
                    tender = parse_tender_detail(detail_page, tender)
                    tender = normalize_tender(tender, source_name, keyword)

                    tender["content_hash"] = make_tender_content_hash(tender)

                    price_number = parse_price_to_number(tender.get("price"))

                    print("Parser-dən sonra:")
                    print("Title:", tender.get("title"))
                    print("Organization:", tender.get("organization"))
                    print("Price:", tender.get("price"))
                    print("Oxunan qiymət:", price_number)
                    print("Publish date:", get_publish_date(tender))
                    print("Content hash:", tender.get("content_hash"))

                    if is_old_publish_date(tender):
                        print("Keçildi: paylaşılma tarixi köhnədir və ya tapılmadı.")
                        print("Paylaşılma tarixi:", get_publish_date(tender))
                        print("Minimum tarix:", MIN_PUBLISH_DATE.strftime("%d.%m.%Y"))
                        continue

                    if is_price_below_minimum(tender):
                        print("Keçildi: qiymət 450k RUB-dan aşağıdır və ya qiymət tapılmadı.")
                        print("Qiymət:", tender.get("price"))
                        print("Oxunan qiymət:", price_number)
                        print("Minimum qiymət:", MIN_PRICE_RUB)
                        continue

                    print("\nUyğun tender tapıldı. Telegram-a göndərilir:")
                    print("Title:", tender.get("title"))
                    print("URL:", tender.get("url"))
                    print("Qiymət:", tender.get("price"))
                    print("Oxunan qiymət:", price_number)
                    print("AZN ekvivalenti:", price_number * rub_to_azn_rate)

                    sent = send_to_telegram(tender, rub_to_azn_rate)

                    if sent:
                        print("Test tender Telegram-a göndərildi.")
                    else:
                        print("Test tender Telegram-a göndərilə bilmədi.")

                    return

                except Exception as e:
                    print("[TEST ITEM ERROR]", tender.get("url"), "|", e)
                    continue

                finally:
                    try:
                        detail_page.close()
                    except Exception:
                        pass

            print("\nŞərtlərə uyğun tender tapılmadı.")
            print("Yoxlanılan şərtlər:")
            print("- paylaşılma tarixi son 1 həftə içində olmalıdır")
            print("- qiymət tapılmalıdır")
            print("- qiymət 450 000 RUB və yuxarı olmalıdır")

        finally:
            browser.close()


if __name__ == "__main__":
    send_first_valid_test_tender()
