import os
import re
import time
from datetime import date, timedelta
from urllib.parse import urljoin


SOURCE_NAME = "win.myseldon.com"
BASE_URL = "https://win.myseldon.com"

SELDON_GRID_URL = os.getenv(
    "SELDON_GRID_URL",
    "https://win.myseldon.com/tender/grid/fz44"
)

SELDON_MAX_PAGES = int(os.getenv("SELDON_MAX_PAGES", "1"))
SELDON_MAX_ITEMS_PER_KEYWORD = int(os.getenv("SELDON_MAX_ITEMS_PER_KEYWORD", "10"))

MIN_PRICE_RUB = int(os.getenv("MIN_PRICE_RUB", "450000"))
MIN_DEADLINE_DATE = date.today() + timedelta(days=3)


EXCLUDED_TITLE_WORDS = [
    "медицин",
    "лекарств",
    "лекарство",
    "фарма",
    "фармацевт",
    "лаборатор",
    "анализ",
    "исследован",
    "пациент",
    "денталь",
    "протез",

    "поставка продуктов",
    "продуктов питания",
    "питание",
    "пищ",
    "хлеб",
    "молоко",
    "мясо",
    "овощ",
    "фрукт",

    "нефтепродукт",
    "нефть",
    "топливо",
    "бензин",
    "дизель",
    "гсм",

    "строитель",
    "строительство",
    "ремонт помещения",
    "капитальный ремонт",
    "текущий ремонт",
    "монтаж",
    "демонтаж",
    "кровля",
    "фасад",
    "асфальт",

    "уборка",
    "клининг",
    "дезинфек",
    "охрана",
    "сторож",

    "контейнерной площадки",
    "мусор",
    "отходов",
    "микроскоп",
]


PRICE_LABELS = [
    "Начальная цена",
    "НМЦК",
    "Начальная максимальная цена",
    "Начальная максимальная цена контракта",
    "Начальная (максимальная) цена контракта",
    "Начальная (максимальная) цена",
    "Цена контракта",
    "Цена",
]


PRICE_STOP_LABELS = [
    "Обеспечение заявки",
    "Обеспечение контракта",
    "Конечная цена",
    "Валюта",
    "Организатор",
    "Заказчик",
    "ИНН",
    "Регион",
    "E-mail",
    "ЭТП",
    "Ссылка",
    "Проведение аукциона",
    "Дата изменения",
    "Тип закупки",
    "Тип закупки с ЕИС",
    "Статус",
    "Осталось дней",
    "Начало приема",
    "Окончание приема",
    "Способ закупки",
    "Наименование",
    "Полное наименование",
]


def clean_text(value):
    if not value:
        return ""

    value = str(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def split_lines(value):
    if not value:
        return []

    value = str(value).replace("\xa0", " ")

    return [
        clean_text(line)
        for line in value.splitlines()
        if clean_text(line)
    ]


def safe_inner_text(locator, timeout=5000):
    try:
        return clean_text(locator.inner_text(timeout=timeout))
    except Exception:
        return ""


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


def parse_price_to_number(value):
    if not value:
        return 0

    text = str(value).lower()
    text = text.replace("\xa0", " ")
    text = text.replace("₽", "")
    text = text.replace("руб.", "")
    text = text.replace("руб", "")
    text = text.replace("рублей", "")
    text = text.replace("ruble", "")
    text = text.replace("rub", "")
    text = text.replace("rur", "")

    matches = re.findall(
        r"\d{1,3}(?:[\s]\d{3})+(?:[,.]\d{1,2})?|\d{6,}(?:[,.]\d{1,2})?",
        text
    )

    numbers = []

    for item in matches:
        number_text = item.replace(" ", "").replace(",", ".")

        try:
            number = float(number_text)
        except Exception:
            continue

        if number > 0:
            numbers.append(number)

    if not numbers:
        return 0

    return max(numbers)


def format_price_rub(price_number):
    try:
        price_number = float(price_number)
    except Exception:
        return ""

    return f"{int(price_number):,}".replace(",", " ") + " ₽"


def is_title_excluded(title):
    title = clean_text(title).lower()

    if not title:
        return True

    for word in EXCLUDED_TITLE_WORDS:
        if word.lower() in title:
            return True

    return False


def fill_input(locator, value):
    locator.click(timeout=10000)
    locator.press("Control+A")
    locator.fill(str(value))
    locator.press("Enter")


def close_possible_modals(page):
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(700)
    except Exception:
        pass

    for text in ["Понятно", "Закрыть", "OK", "Ok"]:
        try:
            page.get_by_text(text, exact=True).click(timeout=1500)
            page.wait_for_timeout(700)
        except Exception:
            pass


def apply_real_seldon_filter(page, keyword):
    print("[SELDON] Filter düyməsi axtarılır...")

    close_possible_modals(page)

    page.get_by_text("Фильтр", exact=True).click(timeout=30000)
    page.wait_for_selector('[data-testid="filter-modal"]', timeout=30000)

    print("[SELDON] Filter modal açıldı")

    subject_input = page.locator('[data-testid="filter-subject-or-input"]')
    fill_input(subject_input, keyword)

    print("[SELDON] Keyword yazıldı:", keyword)

    price_input = page.locator('[data-testid="filter-start-price-input-range-0"]')
    fill_input(price_input, str(MIN_PRICE_RUB))

    print("[SELDON] Minimum qiymət yazıldı:", MIN_PRICE_RUB)

    page.wait_for_timeout(1000)

    page.locator('[data-testid="filter-button-apply"]').click(timeout=30000)

    print("[SELDON] Применить klikləndi")

    try:
        page.wait_for_load_state("networkidle", timeout=25000)
    except Exception:
        pass

    page.wait_for_timeout(7000)

    print("[SELDON] Filter tətbiq olundu.")
    print("[SELDON] Grid URL:", page.url)


def get_page_url_by_number(page_number):
    if page_number <= 1:
        return SELDON_GRID_URL

    if "page=" in SELDON_GRID_URL:
        return re.sub(r"page=\d+", f"page={page_number}", SELDON_GRID_URL)

    separator = "&" if "?" in SELDON_GRID_URL else "?"

    return f"{SELDON_GRID_URL}{separator}page={page_number}"


def extract_dates_from_text(text):
    if not text:
        return []

    return re.findall(r"\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}", text)


def extract_grid_row_info_from_anchor(anchor):
    try:
        data = anchor.evaluate(
            """
            node => {
                function visibleText(el) {
                    if (!el) return "";
                    return (el.innerText || el.textContent || "").replace(/\\s+/g, " ").trim();
                }

                function findRow(el) {
                    let current = el;

                    for (let i = 0; i < 15 && current; i++) {
                        const cells = Array.from(
                            current.querySelectorAll(
                                '[role="gridcell"], [role="cell"], td, div[class*="cell"], div[class*="Cell"]'
                            )
                        );

                        const rowText = visibleText(current);

                        const hasDates = /\\d{2}\\.\\d{2}\\.\\d{4}\\s+\\d{2}:\\d{2}/.test(rowText);
                        const hasPrice = /\\d{1,3}(?:\\s\\d{3})+,\\d{2}/.test(rowText);
                        const hasManyCells = cells.length >= 8;

                        if (hasManyCells && hasDates && hasPrice) {
                            return current;
                        }

                        const role = current.getAttribute && current.getAttribute("role");

                        if ((role === "row" || current.tagName === "TR") && hasPrice) {
                            return current;
                        }

                        current = current.parentElement;
                    }

                    return null;
                }

                const row = findRow(node);

                if (!row) {
                    return {
                        rowText: visibleText(node),
                        cells: [],
                        titleText: visibleText(node)
                    };
                }

                let cellNodes = Array.from(
                    row.querySelectorAll(
                        '[role="gridcell"], [role="cell"], td, div[class*="cell"], div[class*="Cell"]'
                    )
                );

                let cells = cellNodes
                    .map(visibleText)
                    .filter(Boolean);

                return {
                    rowText: visibleText(row),
                    cells: cells,
                    titleText: visibleText(node)
                };
            }
            """
        )
    except Exception:
        return {
            "rowText": "",
            "cells": [],
            "titleText": "",
        }

    return data or {
        "rowText": "",
        "cells": [],
        "titleText": "",
    }


def extract_price_from_grid_cells(cells, row_text):
    candidates = []

    for cell in cells:
        cell = clean_text(cell)

        if not cell:
            continue

        if re.search(r"\d{2}\.\d{2}\.\d{4}", cell):
            continue

        if re.fullmatch(r"\d{1,3}%?", cell):
            continue

        number = parse_price_to_number(cell)

        if number >= MIN_PRICE_RUB:
            candidates.append(number)

    if candidates:
        return max(candidates)

    row_text = clean_text(row_text)

    matches = re.findall(
        r"\d{1,3}(?:\s\d{3})+(?:[,.]\d{1,2})?",
        row_text
    )

    for item in matches:
        number = parse_price_to_number(item)

        if number >= MIN_PRICE_RUB:
            candidates.append(number)

    if candidates:
        return max(candidates)

    return 0


def extract_deadline_from_grid_cells(cells, row_text):
    dates = []

    for cell in cells:
        dates.extend(extract_dates_from_text(cell))

    if not dates:
        dates = extract_dates_from_text(row_text)

    if len(dates) >= 2:
        return clean_text(dates[1])

    if len(dates) == 1:
        return clean_text(dates[0])

    return ""


def extract_publish_date_from_grid_cells(cells, row_text):
    dates = []

    for cell in cells:
        dates.extend(extract_dates_from_text(cell))

    if not dates:
        dates = extract_dates_from_text(row_text)

    if dates:
        return clean_text(dates[0])

    return ""


def extract_tender_type_from_grid_cells(cells):
    for cell in cells:
        value = clean_text(cell)

        if not value:
            continue

        lowered = value.lower()

        if "конкурс" in lowered or "аукцион" in lowered or "запрос" in lowered or "котиров" in lowered:
            return value

    return ""


def extract_grid_items(page):
    items = []
    seen_urls = set()

    try:
        page.wait_for_timeout(3000)

        page.wait_for_selector('a[href*="/tender/"]', timeout=30000)

        anchors = page.locator('a[href*="/tender/"]')
        count = anchors.count()

        for i in range(count):
            anchor = anchors.nth(i)

            try:
                href = anchor.get_attribute("href")
            except Exception:
                continue

            if not href:
                continue

            full_url = urljoin(BASE_URL, href)

            if "/tender/" not in full_url:
                continue

            if "/grid/" in full_url:
                continue

            if full_url in seen_urls:
                continue

            seen_urls.add(full_url)

            row_data = extract_grid_row_info_from_anchor(anchor)

            row_text = clean_text(row_data.get("rowText"))
            cells = row_data.get("cells") or []

            title = clean_text(row_data.get("titleText"))

            if not title:
                title = safe_inner_text(anchor, timeout=3000)

            price_number = extract_price_from_grid_cells(cells, row_text)
            deadline = extract_deadline_from_grid_cells(cells, row_text)
            publish_date = extract_publish_date_from_grid_cells(cells, row_text)
            tender_type = extract_tender_type_from_grid_cells(cells)

            items.append({
                "url": full_url,
                "title": clean_text(title),
                "price_number": price_number,
                "price": format_price_rub(price_number) if price_number else "",
                "publish_date": clean_text(publish_date),
                "deadline": clean_text(deadline),
                "tender_type": clean_text(tender_type),
                "row_text": row_text,
                "cells": cells,
            })

    except Exception as e:
        print(f"[SELDON] Grid item-lər oxunmadı: {e}")

    return items


def extract_value_after_label_by_lines(text, labels, stop_labels=None):
    lines = split_lines(text)

    if stop_labels is None:
        stop_labels = [
            "Краткое наименование",
            "Заказчик",
            "Организатор",
            "Начальная цена",
            "НМЦК",
            "Статус",
            "Осталось дней",
            "Начало приема",
            "Окончание приема",
            "Способ закупки",
            "Тип закупки",
            "ИНН",
            "Регион",
            "E-mail",
            "ЭТП",
            "Ссылка",
            "Проведение аукциона",
        ]

    labels_lower = [x.lower() for x in labels]
    stop_lower = [x.lower() for x in stop_labels]

    for index, line in enumerate(lines):
        lowered = line.lower()

        for label in labels_lower:
            if lowered == label:
                collected = []

                for next_line in lines[index + 1:index + 10]:
                    next_lower = next_line.lower()

                    if any(next_lower.startswith(stop) for stop in stop_lower):
                        break

                    collected.append(next_line)

                    if len(" ".join(collected)) > 80:
                        break

                return clean_text(" ".join(collected))

            if lowered.startswith(label + ":"):
                return clean_text(line.split(":", 1)[1])

    return ""


def extract_date_after_label(text, labels):
    value = extract_value_after_label_by_lines(text, labels)

    if value and parse_date_from_text(value):
        return value

    lines = split_lines(text)
    labels_lower = [x.lower() for x in labels]

    for index, line in enumerate(lines):
        lowered = line.lower()

        if any(label in lowered for label in labels_lower):
            nearby = " ".join(lines[index:index + 6])
            dates = extract_dates_from_text(nearby)

            if dates:
                return clean_text(dates[0])

    return ""


def extract_price_from_detail_text(body_text):
    if not body_text:
        return "", 0

    lines = split_lines(body_text)
    labels_lower = [x.lower() for x in PRICE_LABELS]
    stop_lower = [x.lower() for x in PRICE_STOP_LABELS]

    for index, line in enumerate(lines):
        lowered = line.lower()

        matched_label = None

        for label in labels_lower:
            if lowered == label or lowered.startswith(label + ":") or label in lowered:
                matched_label = label
                break

        if not matched_label:
            continue

        chunks = [line]

        for next_line in lines[index + 1:index + 12]:
            next_lower = next_line.lower()

            if any(next_lower.startswith(stop) for stop in stop_lower):
                break

            chunks.append(next_line)

            joined = " ".join(chunks)

            if parse_price_to_number(joined):
                break

        candidate_text = clean_text(" ".join(chunks))
        price_number = parse_price_to_number(candidate_text)

        if price_number:
            return candidate_text, price_number

    normalized_text = clean_text(body_text)

    for label in PRICE_LABELS:
        pattern = (
            re.escape(label)
            + r".{0,160}?("
            + r"\d{1,3}(?:\s\d{3})+(?:[,.]\d{1,2})?"
            + r"|\d{6,}(?:[,.]\d{1,2})?"
            + r")"
        )

        match = re.search(pattern, normalized_text, re.IGNORECASE)

        if match:
            candidate_text = clean_text(match.group(0))
            price_number = parse_price_to_number(candidate_text)

            if price_number:
                return candidate_text, price_number

    return "", 0


def extract_price_from_detail_page(detail_page):
    """
    Detail səhifədə qiyməti DOM-dan götürür.

    Bu funksiya grid/table qiymətini əsas götürmür.
    Əsas prioritet detail səhifədə görünən bu blokdur:

        Начальная цена
        4 486 160,01 RUB

    Qayda:
    1. 'Начальная цена' label-i tapılır.
    2. Eyni row/parent daxilində label-dən SONRA gələn qiymət götürülür.
    3. 'Обеспечение заявки', 'Обеспечение контракта', 'Конечная цена'
       kimi rəqəmlər qiymət kimi götürülmür.
    """

    js = """
    () => {
        const labels = [
            'Начальная цена',
            'НМЦК',
            'Начальная максимальная цена',
            'Начальная максимальная цена контракта',
            'Начальная (максимальная) цена контракта',
            'Начальная (максимальная) цена',
            'Цена контракта'
        ];

        const badWords = [
            'Обеспечение заявки',
            'Обеспечение контракта',
            'Конечная цена'
        ];

        function normalize(value) {
            return (value || '')
                .replace(/\\u00a0/g, ' ')
                .replace(/\\s+/g, ' ')
                .trim();
        }

        function isVisible(el) {
            if (!el) return false;

            const style = window.getComputedStyle(el);

            if (
                style.display === 'none' ||
                style.visibility === 'hidden' ||
                Number(style.opacity) === 0
            ) {
                return false;
            }

            const rect = el.getBoundingClientRect();

            return rect.width > 0 && rect.height > 0;
        }

        function getText(el) {
            if (!el) return '';
            return normalize(el.innerText || el.textContent || '');
        }

        function extractPrice(value) {
            value = normalize(value);

            const match = value.match(
                /\\d{1,3}(?:\\s\\d{3})+(?:[,.]\\d{1,2})?\\s*(?:RUB|руб\\.?|₽)?|\\d{6,}(?:[,.]\\d{1,2})?\\s*(?:RUB|руб\\.?|₽)?/i
            );

            return match ? normalize(match[0]) : '';
        }

        function cutBeforeBadWords(value) {
            let result = normalize(value);

            for (const badWord of badWords) {
                const index = result.toLowerCase().indexOf(badWord.toLowerCase());

                if (index !== -1) {
                    result = result.slice(0, index);
                }
            }

            return result;
        }

        function extractPriceAfterLabel(value, label) {
            value = normalize(value);

            const lowerValue = value.toLowerCase();
            const lowerLabel = label.toLowerCase();

            const labelIndex = lowerValue.indexOf(lowerLabel);

            if (labelIndex === -1) {
                return '';
            }

            let afterLabel = value.slice(labelIndex + label.length);
            afterLabel = cutBeforeBadWords(afterLabel);

            return extractPrice(afterLabel);
        }

        function directChildrenText(parent) {
            if (!parent) return [];

            return Array.from(parent.children)
                .filter(isVisible)
                .map(getText)
                .filter(Boolean);
        }

        const allElements = Array.from(document.querySelectorAll('body *')).filter(isVisible);

        for (const label of labels) {
            const labelLower = label.toLowerCase();

            const labelNodes = allElements.filter(el => {
                const text = getText(el);
                const lower = text.toLowerCase();

                if (!text) return false;
                if (text.length > 250) return false;

                return lower === labelLower || lower.includes(labelLower);
            });

            for (const node of labelNodes) {
                const nodeText = getText(node);

                // 1. Label və qiymət eyni elementdədirsə,
                // yalnız label-dən sonrakı hissədən qiymət götür.
                const ownPrice = extractPriceAfterLabel(nodeText, label);

                if (ownPrice) {
                    return {
                        priceText: ownPrice,
                        sourceText: nodeText,
                        method: 'own_text_after_label'
                    };
                }

                // 2. Screenshot-dakı əsas hal:
                // parent direct children:
                // [Начальная цена] [4 486 160,01 RUB]
                let parent = node.parentElement;

                for (let level = 0; level < 8 && parent; level++) {
                    if (!isVisible(parent)) {
                        parent = parent.parentElement;
                        continue;
                    }

                    const children = directChildrenText(parent);
                    const parentText = getText(parent);

                    const labelChildIndex = children.findIndex(text => {
                        const lower = text.toLowerCase();

                        return lower === labelLower || lower.includes(labelLower);
                    });

                    if (labelChildIndex !== -1) {
                        for (let i = labelChildIndex + 1; i < children.length; i++) {
                            const candidate = children[i];
                            const candidateLower = candidate.toLowerCase();

                            if (
                                badWords.some(word =>
                                    candidateLower.includes(word.toLowerCase())
                                )
                            ) {
                                break;
                            }

                            const price = extractPrice(candidate);

                            if (price) {
                                return {
                                    priceText: price,
                                    sourceText: parentText,
                                    method: 'parent_direct_child_after_label'
                                };
                            }
                        }
                    }

                    // 3. Parent text-də label və qiymət birlikdədirsə,
                    // yenə yalnız label-dən sonrakı hissədən oxu.
                    if (
                        parentText.toLowerCase().includes(labelLower) &&
                        parentText.length < 1200
                    ) {
                        const price = extractPriceAfterLabel(parentText, label);

                        if (price) {
                            return {
                                priceText: price,
                                sourceText: parentText,
                                method: 'parent_text_after_label'
                            };
                        }
                    }

                    parent = parent.parentElement;
                }

                // 4. Label-in sibling-lərində qiymət varsa.
                let current = node;

                for (let level = 0; level < 6 && current; level++) {
                    let sibling = current.nextElementSibling;

                    for (let i = 0; i < 8 && sibling; i++) {
                        if (!isVisible(sibling)) {
                            sibling = sibling.nextElementSibling;
                            continue;
                        }

                        const siblingText = getText(sibling);
                        const siblingLower = siblingText.toLowerCase();

                        if (
                            siblingText &&
                            !badWords.some(word =>
                                siblingLower.includes(word.toLowerCase())
                            )
                        ) {
                            const price = extractPrice(siblingText);

                            if (price) {
                                return {
                                    priceText: price,
                                    sourceText: siblingText,
                                    method: 'next_sibling_price'
                                };
                            }
                        }

                        sibling = sibling.nextElementSibling;
                    }

                    current = current.parentElement;
                }
            }
        }

        return {
            priceText: '',
            sourceText: '',
            method: ''
        };
    }
    """

    try:
        data = detail_page.evaluate(js)
    except Exception as e:
        print("[SELDON] Detail DOM qiymət oxunmadı:", e)
        return "", 0

    if not data:
        return "", 0

    price_text = clean_text(data.get("priceText"))
    source_text = clean_text(data.get("sourceText"))
    method = clean_text(data.get("method"))

    price_number = parse_price_to_number(price_text)

    if price_number:
        print("[SELDON] Qiymət detail DOM-dan götürüldü:", price_text)
        print("[SELDON] Qiymət DOM method:", method)
        print("[SELDON] Qiymət source:", source_text[:300])
        return price_text, price_number

    return "", 0

def get_title_from_detail_page(detail_page):
    body_text_before = safe_inner_text(detail_page.locator("body").first, timeout=10000)

    try:
        detail_page.get_by_text("Полное наименование", exact=False).first.click(
            timeout=7000,
            force=True
        )
        detail_page.wait_for_timeout(1200)
        print("[SELDON] Полное наименование force klikləndi.")
    except Exception as e:
        print(f"[SELDON] Полное наименование klik alınmadı, fallback istifadə olunur: {e}")

    body_text = safe_inner_text(detail_page.locator("body").first, timeout=10000)

    if not body_text:
        body_text = body_text_before

    title = extract_value_after_label_by_lines(
        body_text,
        [
            "Полное наименование",
            "Наименование закупки",
            "Наименование",
            "Предмет закупки",
        ],
        stop_labels=[
            "Краткое наименование",
            "Заказчик",
            "Организатор",
            "Начальная цена",
            "НМЦК",
            "Статус",
            "Осталось дней",
            "Начало приема",
            "Окончание приема",
            "Способ закупки",
            "Тип закупки",
        ]
    )

    title = clean_text(title)

    if title and len(title) > 10:
        return title

    h1_title = safe_inner_text(detail_page.locator("h1").first, timeout=5000)

    if h1_title and len(h1_title) > 10:
        return h1_title

    return ""


def parse_seldon_detail(page, grid_item, keyword):
    detail_url = grid_item.get("url")

    grid_title = clean_text(grid_item.get("title"))
    grid_price_number = grid_item.get("price_number") or 0
    grid_price = clean_text(grid_item.get("price"))
    grid_deadline = clean_text(grid_item.get("deadline"))
    grid_publish_date = clean_text(grid_item.get("publish_date"))
    grid_tender_type = clean_text(grid_item.get("tender_type"))

    detail_page = page.context.new_page()

    try:
        detail_page.goto(detail_url, wait_until="networkidle", timeout=60000)
        detail_page.wait_for_timeout(3000)

        body_text = safe_inner_text(detail_page.locator("body").first, timeout=15000)

        if not body_text:
            print("[SELDON] Detail body boşdur:", detail_url)
            return None

        title = get_title_from_detail_page(detail_page)

        body_text_after_title = safe_inner_text(detail_page.locator("body").first, timeout=15000)

        if body_text_after_title:
            body_text = body_text_after_title

        if not title:
            title = grid_title

        title = clean_text(title)

        if not title:
            print("[SELDON] Keçildi, title tapılmadı:", detail_url)
            return None

        if is_title_excluded(title):
            print("[SELDON] Keçildi, title exclude filter:", title)
            return None

        detail_price_text, price_number = extract_price_from_detail_page(detail_page)

        if price_number:
            print("[SELDON] Qiymət detail DOM-dan götürüldü:", detail_price_text)
        else:
            detail_price_text, price_number = extract_price_from_detail_text(body_text)

            if price_number:
                print("[SELDON] Qiymət detail text-dən götürüldü:", detail_price_text)
            else:
                price_number = grid_price_number
                print("[SELDON] Qiymət detail-də tapılmadı, grid fallback istifadə olundu:", grid_price)

        if not price_number:
            print("[SELDON] Keçildi, qiymət tapılmadı:", title)
            print("[SELDON] Detail price text:", detail_price_text)
            print("[SELDON] Grid price:", grid_price)
            return None

        if price_number < MIN_PRICE_RUB:
            print("[SELDON] Keçildi, qiymət aşağıdır:", title, price_number)
            return None

        price = format_price_rub(price_number)

        status = extract_value_after_label_by_lines(
            body_text,
            [
                "Статус",
                "Состояние",
                "Этап закупки",
            ]
        )

        status = clean_text(status)

        status_lower = status.lower()

        if any(word in status_lower for word in ["отменён", "отменен", "завершён", "завершен"]):
            print("[SELDON] Keçildi, status uyğun deyil:", status)
            return None

        deadline = extract_date_after_label(
            body_text,
            [
                "Окончание приема заявок",
                "Окончание подачи заявок",
                "Дата окончания подачи заявок",
                "Срок подачи заявок",
            ]
        )

        if not deadline:
            deadline = grid_deadline
            print("[SELDON] Son tarix grid-dən götürüldü:", deadline)

        deadline_date = parse_date_from_text(deadline)

        if deadline_date is None:
            print("[SELDON] Keçildi, son tarix tapılmadı:", title)
            print("[SELDON] Grid deadline:", grid_deadline)
            return None

        if deadline_date < MIN_DEADLINE_DATE:
            print("[SELDON] Keçildi, son tarix yaxındır:", title, deadline)
            return None

        publish_date = extract_date_after_label(
            body_text,
            [
                "Начало приема заявок",
                "Дата публикации",
                "Дата объявления",
                "Дата размещения",
            ]
        )

        if not publish_date:
            publish_date = grid_publish_date

        tender_type = extract_value_after_label_by_lines(
            body_text,
            [
                "Способ закупки",
                "Тип закупки",
                "Тип закупки с ЕИС",
                "Процедура",
            ]
        )

        if not tender_type:
            tender_type = grid_tender_type

        organization = extract_value_after_label_by_lines(
            body_text,
            [
                "Организатор",
                "Заказчик",
                "Наименование заказчика",
                "Покупатель",
            ]
        )

        return {
            "source": SOURCE_NAME,
            "keyword": keyword,
            "title": title,
            "url": detail_url,
            "price": price,
            "status": clean_text(status) or "Yoxdur",
            "deadline": clean_text(deadline),
            "application_end": clean_text(deadline),
            "publish_date": clean_text(publish_date) or "Yoxdur",
            "tender_type": clean_text(tender_type) or "Yoxdur",
            "type": clean_text(tender_type) or "Yoxdur",
            "organization": clean_text(organization) or "Yoxdur",
            "customer": clean_text(organization) or "Yoxdur",
            "title_links": [],
        }

    except Exception as e:
        print(f"[SELDON] Detail parse error: {detail_url} | {e}")
        return None

    finally:
        try:
            detail_page.close()
        except Exception:
            pass


def search_seldon(page, keyword):
    results = []

    print("[SELDON] Başladı")
    print("[SELDON] Keyword:", keyword)
    print("[SELDON] Grid URL:", SELDON_GRID_URL)

    checked_urls = set()

    try:
        for page_number in range(1, SELDON_MAX_PAGES + 1):
            grid_url = get_page_url_by_number(page_number)

            print(f"[SELDON] Grid açılır: page={page_number}")
            print("[SELDON] URL:", grid_url)

            page.goto(grid_url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(5000)

            close_possible_modals(page)

            body_text = safe_inner_text(page.locator("body").first, timeout=10000)

            if "Войти" in body_text and "Государственные" not in body_text:
                print("[SELDON] Login səhifəsi göründü. Bu source login olmadan işləməlidir.")
                return results

            if page_number == 1:
                apply_real_seldon_filter(page, keyword)

            grid_items = extract_grid_items(page)

            print(f"[SELDON] Grid item sayı: {len(grid_items)}")

            for item in grid_items:
                detail_url = item.get("url")

                if not detail_url:
                    continue

                if detail_url in checked_urls:
                    continue

                checked_urls.add(detail_url)

                print("[SELDON] Grid title:", item.get("title"))
                print("[SELDON] Grid price:", item.get("price"))
                print("[SELDON] Grid price number:", item.get("price_number"))
                print("[SELDON] Grid deadline:", item.get("deadline"))
                print("[SELDON] Grid publish date:", item.get("publish_date"))
                print("[SELDON] Detail URL:", detail_url)

                tender = parse_seldon_detail(page, item, keyword)

                if not tender:
                    continue

                results.append(tender)

                print("[SELDON] Uyğun tender tapıldı:")
                print(tender["title"])
                print(tender["url"])
                print("Qiymət:", tender.get("price"))
                print("Son tarix:", tender.get("deadline"))

                if len(results) >= SELDON_MAX_ITEMS_PER_KEYWORD:
                    print("[SELDON] Limit doldu.")
                    return results

            time.sleep(1)

    except Exception as e:
        print(f"[SELDON] Search error: {e}")

    print("[SELDON] Bitdi. Tapılan tender sayı:", len(results))

    return results
