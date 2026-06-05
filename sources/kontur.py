import re
from datetime import date, timedelta
from urllib.parse import quote_plus


SOURCE_NAME = "zakupki.kontur.ru"

BASE_URL = "https://zakupki.kontur.ru/regions/sibir"

# Son 3 gün içində paylaşılan tenderlər
PUBLISH_DATE_DAYS = 3

MIN_PRICE = 450000

BASE_QUERY = (
    "q.ApplicationDeadlineType=All"
    "&q.ExcludeInns=false"
    "&q.ISCategoryIds="
    "&q.Laws=0%2C1%2C4%2C2%2C5%2C6"
    f"&q.MaxPrice.From={MIN_PRICE}"
    "&q.PurchaseStatuses=1%2C2%2C3%2C4%2C5"
    "&q.Smp=All"
    "&q.SortOrder=2"
    "&q.RegionIds=19b32b46-8868-47a1-8098-b40719cdc43e%2Cccddbc38-f962-4167-b62a-79776c9e853d%2Cbe121c99-c8e3-4097-9302-0a2306f48097%2C9f7e3f45-8e4a-4b35-9bd3-70e58f5219ae%2C69d9e4ae-d749-4f17-9463-53ddd6571163%2C0367f896-ec0d-48ca-ae18-aee928559e9b%2C125a15f7-bfa5-410b-86d5-e195dd83fb35%2Ca3036811-5d1a-4bb5-bad0-18eabbc9634b%2C4fc67445-3d08-4c1b-ac91-70ff53248d4d"
)

TENDER_PATTERN = re.compile(r"^https://zakupki\.kontur\.ru/[A-Z0-9-]+$")

ALLOWED_TITLE_WORDS = [
    "сайт",
    "веб-сайт",
    "интернет-сайт",
    "портал",
    "веб-портал",
    "личный кабинет",
    "информационная система",
    "программное обеспечение",
    "модернизация сайта",
    "доработка сайта",
    "сопровождение сайта",
    "техническая поддержка сайта",
    "разработка сайта",
    "создание сайта",
]

EXCLUDED_TITLE_WORDS = [
    "лабораторных исследований",
    "медицин",
    "фарма",
    "лекарств",
    "оборудован",
    "поставка",
    "питание",
    "ремонт помещения",
    "строитель",
    "охрана",
    "уборка",
]


def get_publish_date_range():
    publish_date_to = date.today()
    publish_date_from = publish_date_to - timedelta(days=PUBLISH_DATE_DAYS)

    return (
        publish_date_from.strftime("%d.%m.%Y"),
        publish_date_to.strftime("%d.%m.%Y"),
    )


def build_search_url(keyword):
    encoded_keyword = quote_plus(keyword)

    publish_date_from, publish_date_to = get_publish_date_range()

    return (
        f"{BASE_URL}?"
        f"{BASE_QUERY}"
        f"&q.PublishDateFrom={publish_date_from}"
        f"&q.PublishDateTo={publish_date_to}"
        f"&q.Text={encoded_keyword}"
    )


def normalize_text(text):
    if not text:
        return ""

    return " ".join(
        text.replace("\n", " ")
        .replace("\t", " ")
        .split()
    )


def is_allowed_title(title):
    title_lower = title.lower()

    has_allowed_word = any(
        word in title_lower
        for word in ALLOWED_TITLE_WORDS
    )

    has_excluded_word = any(
        word in title_lower
        for word in EXCLUDED_TITLE_WORDS
    )

    return has_allowed_word and not has_excluded_word


def parse_kontur_page_links(page, keyword, seen_urls):
    try:
        links = page.locator("a").evaluate_all("""
            elements => elements.map(a => ({
                text: a.innerText,
                href: a.href
            }))
        """)
    except Exception as e:
        print(f"[KONTUR LINKS ERROR] Keyword: {keyword} | {e}")
        return []

    tenders = []

    for link in links:
        title = normalize_text(link.get("text", ""))
        tender_url = link.get("href", "")

        if not tender_url:
            continue

        if tender_url in seen_urls:
            continue

        if not TENDER_PATTERN.match(tender_url):
            continue

        if not title:
            continue

        if not is_allowed_title(title):
            continue

        seen_urls.add(tender_url)

        tenders.append({
            "source": SOURCE_NAME,
            "keyword": keyword,
            "title": title,
            "url": tender_url,

            "organization": None,
            "price": None,
            "tender_type": None,
            "status": None,
            "deadline": None,
            "publish_date": None,

            "review_end_date": None,
            "documents": [],
            "title_links": [],
        })

    return tenders


def search_kontur(page, keyword):
    seen_urls = set()

    publish_date_from, publish_date_to = get_publish_date_range()

    print("[KONTUR] PublishDateFrom:", publish_date_from)
    print("[KONTUR] PublishDateTo:", publish_date_to)
    print("[KONTUR] Min price:", MIN_PRICE)

    url = build_search_url(keyword)

    print("[KONTUR] URL açılır:")
    print(url)

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
    except Exception as e:
        print(f"[KONTUR SEARCH ERROR] Keyword: {keyword} | {e}")
        return []

    tenders = parse_kontur_page_links(page, keyword, seen_urls)

    print("[KONTUR] Tender count:", len(tenders))

    return tenders
