from playwright.sync_api import sync_playwright
from sources.rostender import search_rostender


TEST_KEYWORD = "разработка сайта"


def main():
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

        page = context.new_page()
        page.set_default_timeout(60000)
        page.set_default_navigation_timeout(60000)

        tenders = search_rostender(page, TEST_KEYWORD)

        print("\n========== ROSTENDER TEST NƏTİCƏ ==========")
        print("Keyword:", TEST_KEYWORD)
        print("Tapılan tender sayı:", len(tenders))

        for index, tender in enumerate(tenders, start=1):
            print("\n------------------------------")
            print("№:", index)
            print("Title:", tender.get("title"))
            print("URL:", tender.get("url"))
            print("Source:", tender.get("source"))
            print("Keyword:", tender.get("keyword"))

        page.close()
        browser.close()


if __name__ == "__main__":
    main()
