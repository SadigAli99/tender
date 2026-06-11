import re
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse, parse_qs

SOURCE_NAME = "rostender.info"
BASE_URL = "https://rostender.info"

MAX_ROSTENDER_PAGES = 3

MIN_PRICE_RUB = 450_000
MAX_PRICE_RUB = 100_000_000

# Son müraciət tarixi bugündən minimum 3 gün sonra olsun
DEADLINE_FROM_DAYS = 3

# Elan tarixi son 3 gün içində olsun
PUBLISH_DATE_DAYS = 3


ALLOWED_TITLE_WORDS = [
    "разработка сайта",
    "создание сайта",
    "разработка веб-сайта",
    "создание веб-сайта",
    "разработка интернет-сайта",
    "создание интернет-сайта",
    "модернизация сайта",
    "доработка сайта",
    "сопровождение сайта",
    "техническая поддержка сайта",
    "поддержка сайта",

    "сайт",
    "сайта",
    "сайтов",
    "веб-сайт",
    "веб-сайта",
    "web-сайт",

    "разработка портала",
    "создание портала",
    "разработка веб-портала",
    "создание веб-портала",
    "портал",
    "веб-портал",

    "разработка личного кабинета",
    "создание личного кабинета",
    "личный кабинет",

    "разработка информационной системы",
    "модернизация информационной системы",
    "доработка информационной системы",
    "информационная система",

    "разработка программного обеспечения",
    "доработка программного обеспечения",
    "модернизация программного обеспечения",
    "программное обеспечение",
]


EXCLUDED_TITLE_WORDS = [
    "поставка",
    "мебель",
    "продукты",
    "питание",
    "ремонт помещения",
    "строительство",
    "уборка",
    "канцеляр",
    "медицин",
    "оборудование",
    "одежда",
    "транспорт",
    "охрана",
    "топливо",
    "лекарств",
    "фарма",
    "лабораторных исследований",
]


def normalize_url(href: str) -> str:
    return urljoin(BASE_URL, href)


def clean_text(text: str) -> str:
    if not text:
        return ""

    return " ".join(
        str(text)
        .replace("\n", " ")
        .replace("\t", " ")
        .split()
    )


def get_publish_date_range():
    publish_date_to = date.today()
    publish_date_from = publish_date_to - timedelta(days=PUBLISH_DATE_DAYS)

    return (
        publish_date_from.strftime("%d.%m.%Y"),
        publish_date_to.strftime("%d.%m.%Y")
    )


def get_deadline_from_date() -> str:
    deadline_from = date.today() + timedelta(days=DEADLINE_FROM_DAYS)
    return deadline_from.strftime("%d.%m.%Y")


def is_allowed_title(title: str) -> bool:
    if not title:
        return False

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


def extract_title_from_row(row_text: str) -> str:
    lines = [
        line.strip()
        for line in str(row_text).split("\n")
        if line.strip()
    ]

    for line in lines:
        line_lower = line.lower()

        if line_lower.startswith("тендер"):
            continue

        if line_lower.startswith("окончание"):
            continue

        if line_lower.startswith("начальная цена"):
            continue

        if "₽" in line:
            continue

        if "руб" in line_lower:
            continue

        if "мск" in line_lower:
            continue

        if len(line) > 15:
            return clean_text(line)

    return clean_text(row_text)


def extract_query_hash_from_url(url: str):
    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        query_values = query_params.get("query")

        if query_values:
            return query_values[0]

        return None

    except Exception:
        return None


def build_rostender_page_url(query_hash: str, page_number: int = 1) -> str:
    return f"{BASE_URL}/extsearch/advanced?query={query_hash}&page={page_number}"


def get_total_pages(page):
    total_pages = 1

    try:
        input_max = page.locator('input[name="page"]').get_attribute("max")

        if input_max and str(input_max).isdigit():
            total_pages = max(total_pages, int(input_max))

    except Exception:
        pass

    try:
        page_numbers = page.locator(".pagination a, .pagination span").evaluate_all("""
            elements => elements
                .map(el => (el.innerText || '').trim())
                .filter(text => /^[0-9]+$/.test(text))
                .map(text => parseInt(text, 10))
        """)

        if page_numbers:
            total_pages = max(total_pages, max(page_numbers))

    except Exception as e:
        print(f"[ROSTENDER PAGINATION ERROR] {e}")

    return total_pages


def extract_tender_links(page, keyword="", seen_urls=None):
    if seen_urls is None:
        seen_urls = set()

    try:
        items = page.evaluate("""
            () => {
                const result = [];
                const anchors = Array.from(document.querySelectorAll('a[href]'));

                function decodeHtml(value) {
                    const div = document.createElement('div');
                    div.innerHTML = value || '';
                    return (div.textContent || div.innerText || value || '').trim();
                }

                function findTenderRow(a) {
                    const selectors = [
                        '.tender',
                        '.tender-row',
                        '.tender-item',
                        '.search-results__item',
                        '.list-item',
                        'tr',
                        '.row'
                    ];

                    for (const selector of selectors) {
                        const row = a.closest(selector);
                        if (row) {
                            return row;
                        }
                    }

                    return null;
                }

                function extractLawType(row) {
                    if (!row) {
                        return '';
                    }

                    const infoBlock = row.querySelector('.tender__infographics');

                    if (!infoBlock) {
                        return '';
                    }

                    const elements = Array.from(
                        infoBlock.querySelectorAll('[data-title], [aria-label], [class]')
                    );

                    const rawText = elements
                        .map(el => {
                            return [
                                el.getAttribute('data-title') || '',
                                el.getAttribute('aria-label') || '',
                                String(el.className || '')
                            ].join(' ');
                        })
                        .join(' ');

                    const text = decodeHtml(rawText)
                        .toLowerCase()
                        .replace(/\u00a0/g, ' ')
                        .replace(/ё/g, 'е');

                    // Bu tip tenderlər 44/223 deyil, ona görə bloklanmamalıdır
                    if (
                        text.includes('не регулируемые специальными законами') ||
                        text.includes('не регулируется специальными законами') ||
                        text.includes('не регулируемых специальными законами')
                    ) {
                        return '';
                    }

                    if (
                        text.includes('b-223') ||
                        /(^|[^0-9])223\s*(?:-|–|—)?\s*фз/.test(text)
                    ) {
                        return '223-ФЗ';
                    }

                    if (
                        text.includes('b-44') ||
                        /(^|[^0-9])44\s*(?:-|–|—)?\s*фз/.test(text)
                    ) {
                        return '44-ФЗ';
                    }

                    return '';
                }

                for (const a of anchors) {
                    const href = a.href || '';
                    const text = a.innerText || '';

                    const row = findTenderRow(a);

                    result.push({
                        href: href,
                        text: text,
                        rowText: row ? row.innerText : a.innerText,
                        lawType: extractLawType(row)
                    });
                }

                return result;
            }
        """)
    except Exception as e:
        print(f"[ROSTENDER EXTRACT LINKS ERROR] {e}")
        return []

    tenders = []

    for item in items:
        href = item.get("href", "")
        text = item.get("text", "")
        row_text = item.get("rowText", "")
        law_type = clean_text(item.get("lawType", ""))

        if not href:
            continue

        href_lower = href.lower()

        is_tender_link = (
            "/tender/" in href_lower
            or "tender-" in href_lower
            or re.search(r"/\d{7,}", href_lower)
        )

        if not is_tender_link:
            continue

        tender_url = normalize_url(href)

        if tender_url in seen_urls:
            continue

        title = clean_text(text)

        if not title or len(title) < 10:
            title = extract_title_from_row(row_text)

        if not title:
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
            "law_type": law_type,
            "status": None,
            "deadline": None,
            "publish_date": None,

            "review_end_date": None,
            "documents": [],
            "title_links": [],
        })

    return tenders


def fill_advanced_form(page, keyword: str):
    publish_date_from, publish_date_to = get_publish_date_range()
    deadline_from = get_deadline_from_date()

    print("[ROSTENDER] Advanced keyword:", keyword)
    print("[ROSTENDER] Publish date from:", publish_date_from)
    print("[ROSTENDER] Publish date to:", publish_date_to)
    print("[ROSTENDER] Deadline from:", deadline_from)
    print("[ROSTENDER] Min price:", MIN_PRICE_RUB)
    print("[ROSTENDER] Max price:", MAX_PRICE_RUB)

    page.evaluate(
        """
        ({ keyword, publishDateFrom, publishDateTo, deadlineFrom, minPrice, maxPrice }) => {
            function setValue(selector, value) {
                const el = document.querySelector(selector);
                if (!el) return;

                el.value = value;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }

            setValue('#keywords', keyword);

            // Дата объявления
            setValue('#tender-start-date-from', publishDateFrom);
            setValue('input[name="dtc_from"]', publishDateFrom);

            setValue('#tender-start-date-to', publishDateTo);
            setValue('input[name="dtc_to"]', publishDateTo);

            // Дата окончания приёма заявок
            setValue('#tender-end-date-from', deadlineFrom);
            setValue('input[name="dte_from"]', deadlineFrom);

            setValue('#min_price', String(minPrice));
            setValue('#min_price-disp', String(minPrice));

            setValue('#max_price', String(maxPrice));
            setValue('#max_price-disp', String(maxPrice));

            const states = document.querySelector('#states');

            if (states) {
                Array.from(states.options).forEach(option => {
                    option.selected = ['10', '50'].includes(option.value);
                });

                states.dispatchEvent(new Event('change', { bubbles: true }));
            }

            const completedAll = document.querySelector('input[name="completed_status"][value="all"]');

            if (completedAll) {
                completedAll.checked = true;
                completedAll.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
        """,
        {
            "keyword": keyword,
            "publishDateFrom": publish_date_from,
            "publishDateTo": publish_date_to,
            "deadlineFrom": deadline_from,
            "minPrice": MIN_PRICE_RUB,
            "maxPrice": MAX_PRICE_RUB,
        }
    )


def submit_advanced_search(page):
    page.evaluate("""
        () => {
            const button = document.querySelector('#start-search-button');

            if (!button) {
                throw new Error('start-search-button tapılmadı');
            }

            button.removeAttribute('target');

            const form = button.closest('form');

            if (form) {
                form.removeAttribute('target');
            }
        }
    """)

    page.locator("#start-search-button").click(no_wait_after=True)


def search_rostender(page, keyword: str):
    print("===================================")
    print(f"Keyword: {keyword}")
    print(f"Source: {SOURCE_NAME}")
    print("[ROSTENDER] Advanced search işləyir")

    all_filtered_tenders = []
    seen_urls = set()

    try:
        page.goto(
            f"{BASE_URL}/extsearch/advanced",
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.locator("#keywords").wait_for(
            state="visible",
            timeout=30000
        )

        fill_advanced_form(page, keyword)
        submit_advanced_search(page)

        try:
            page.wait_for_url("**/extsearch/advanced?query=**", timeout=60000)
        except Exception:
            page.wait_for_timeout(5000)

        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(5000)

        query_hash = extract_query_hash_from_url(page.url)

        if not query_hash:
            print("[ROSTENDER] Query hash tapılmadı. Yalnız cari səhifə oxunacaq.")
            total_pages = 1
            pages_to_scan = 1
        else:
            total_pages = get_total_pages(page)
            pages_to_scan = min(total_pages, MAX_ROSTENDER_PAGES)

        print("[ROSTENDER] Current URL:", page.url)
        print("[ROSTENDER] Query hash:", query_hash)
        print("[ROSTENDER] Ümumi səhifə sayı:", total_pages)
        print("[ROSTENDER] Yoxlanılacaq səhifə sayı:", pages_to_scan)

        for page_number in range(1, pages_to_scan + 1):
            if query_hash:
                page_url = build_rostender_page_url(query_hash, page_number)

                print("\n[ROSTENDER] Page açılır:", page_number)
                print(page_url)

                try:
                    page.goto(
                        page_url,
                        wait_until="domcontentloaded",
                        timeout=60000
                    )
                    page.wait_for_timeout(5000)
                except Exception as e:
                    print(f"[ROSTENDER PAGE ERROR] Page: {page_number} | {e}")
                    continue
            else:
                print("\n[ROSTENDER] Page oxunur:", page_number)
                print(page.url)

            raw_tenders = extract_tender_links(
                page=page,
                keyword=keyword,
                seen_urls=seen_urls
            )

            print(f"[ROSTENDER] Page {page_number} raw tender count:", len(raw_tenders))

            if not raw_tenders:
                print(f"[ROSTENDER] Page {page_number} raw tender tapılmadı.")
                continue

            filtered_tenders = [
                tender
                for tender in raw_tenders
                if is_allowed_title(tender["title"])
            ]

            print(f"[ROSTENDER] Page {page_number} filtered tender count:", len(filtered_tenders))

            if filtered_tenders:
                print(f"[ROSTENDER] Page {page_number} filtered tenders:")
                for tender in filtered_tenders:
                    print(f"- {tender['title']}")
                    print(f"  {tender['url']}")
            else:
                print(f"[ROSTENDER] Page {page_number} filtered tender tapılmadı.")

            all_filtered_tenders.extend(filtered_tenders)

        print(f"\n[ROSTENDER] Keyword result count: {keyword} -> {len(all_filtered_tenders)}")

        return all_filtered_tenders

    except Exception as e:
        print(f"[ROSTENDER SEARCH ERROR] Keyword: {keyword} | {e}")
        return []
