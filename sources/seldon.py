import os
import re
import time
from datetime import date, timedelta
from urllib.parse import urljoin

from dotenv import load_dotenv

load_dotenv()


SOURCE_NAME = "win.myseldon.com"
BASE_URL = "https://win.myseldon.com"

SELDON_GRID_URL = os.getenv(
    "SELDON_GRID_URL",
    "https://win.myseldon.com/tender/grid/commercial"
)

SELDON_LOGIN_URL = (
    "https://account.myseldon.com/ru/account/login"
    "?returnUrl=https%3A%2F%2Fwin.myseldon.com"
)

SELDON_LOGIN = os.getenv("SELDON_LOGIN", "").strip()
SELDON_PASSWORD = os.getenv("SELDON_PASSWORD", "").strip()

SELDON_MAX_PAGES = int(os.getenv("SELDON_MAX_PAGES", "1"))
SELDON_MAX_ITEMS_PER_KEYWORD = int(os.getenv("SELDON_MAX_ITEMS_PER_KEYWORD", "10"))

MIN_PRICE_RUB = int(os.getenv("MIN_PRICE_RUB", "450000"))
MIN_DEADLINE_DATE = date.today() + timedelta(days=3)

DEBUG_SELDON = os.getenv("DEBUG_SELDON", "0") == "1"


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


ORGANIZER_FIELD_LABELS = [
    "Организатор",
    "Заказчик",
    "Наименование",
    "Краткое наименование",
    "Полное наименование",
    "Регион",
    "ИНН",
    "Телефон",
    "Электронная почта",
    "Контактное лицо",
    "Источник",
    "Начальная цена",
    "НМЦК",
    "Статус",
    "Осталось дней",
    "Начало приема заявок",
    "Окончание приема заявок",
    "Окончание приёма заявок",
    "Способ закупки",
    "Тип закупки",
    "Общие сведения",
    "Лоты",
    "Документы",
]


# -----------------------------------------------------------------------------
# Common helpers
# -----------------------------------------------------------------------------


def clean_text(value):
    if not value:
        return ""

    value = str(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def clean_multiline_text(value):
    """
    Body text üçün istifadə olunur.
    clean_text-dən fərqi: \n saxlanılır ki, line-based parser label/value bloklarını görə bilsin.
    """
    if not value:
        return ""

    value = str(value).replace("\xa0", " ")
    value = value.replace("\r\n", "\n").replace("\r", "\n")

    lines = []

    for line in value.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()

        if line:
            lines.append(line)

    return "\n".join(lines).strip()


def is_masked_text(value):
    if not value:
        return False

    text = clean_text(value).strip('"').strip("'").strip()

    if not text:
        return False

    masked_chars = ["▒", "█", "■", "*", "•"]
    masked_count = sum(text.count(ch) for ch in masked_chars)

    return masked_count >= 5 and masked_count / max(len(text), 1) > 0.3


def clear_if_masked(value):
    value = clean_text(value)

    if is_masked_text(value):
        return ""

    return value


def is_region_value(value):
    value = clean_text(value).lower()

    if not value:
        return False

    if re.search(r"\b\d{1,3}\s*регион\b", value):
        return True

    region_words = [
        "область",
        "край",
        "республика",
        "автономный округ",
        "город",
        "район",
        "регион",
        "москва",
        "санкт-петербург",
        "севастополь",
    ]

    return any(word in value for word in region_words)


def looks_like_organization_name(value):
    value = clean_text(value)

    if not value:
        return False

    if is_masked_text(value):
        return False

    if is_region_value(value):
        return False

    lowered = value.lower()

    markers = [
        "акционерное общество",
        "ао ",
        " ао",
        "общество с ограниченной ответственностью",
        "ооо ",
        " ооо",
        "публичное акционерное общество",
        "пао ",
        " пао",
        "муниципальное",
        "государственное",
        "федеральное",
        "казенное",
        "бюджетное",
        "автономное",
        "учреждение",
        "предприятие",
        "компания",
    ]

    if any(marker in lowered for marker in markers):
        return True

    # Seldon-da təşkilat adları çox vaxt tam böyük hərflə gəlir.
    if len(value) > 10 and value.upper() == value:
        return True

    return False


def normalize_organization_value(value):
    value = clear_if_masked(value)

    if not value:
        return ""

    if is_region_value(value):
        return ""

    if not looks_like_organization_name(value):
        return ""

    return value


def extract_organization_from_title(title):
    """
    Son fallback. Seldon DOM company blokunu verməsə, title içindəki
    "АО ..." hissəsini ən azı organization kimi çıxarır.
    """
    title = clean_text(title)

    if not title:
        return ""

    patterns = [
        r"\bАО\s+[А-ЯЁA-Z0-9][А-ЯЁA-Zа-яёa-z0-9\-\s\.\"«»]+",
        r"\bПАО\s+[А-ЯЁA-Z0-9][А-ЯЁA-Zа-яёa-z0-9\-\s\.\"«»]+",
        r"\bООО\s+[А-ЯЁA-Z0-9][А-ЯЁA-Zа-яёa-z0-9\-\s\.\"«»]+",
    ]

    stop_words = [
        " по ",
        " для ",
        " на ",
        " при ",
        " в ",
        " и ",
    ]

    for pattern in patterns:
        match = re.search(pattern, title)

        if not match:
            continue

        value = clean_text(match.group(0))

        # Title-in sonundakı qalan sözləri çox uzatmamaq üçün
        # stop sözlərindən əvvəl kəsirik.
        lowered = " " + value.lower() + " "
        cut_at = None

        for stop_word in stop_words:
            index = lowered.find(stop_word, 4)

            if index != -1:
                cut_at = index
                break

        if cut_at:
            value = clean_text(value[:cut_at - 1])

        value = value.strip(" .,-;:")

        if normalize_organization_value(value):
            return value

    return ""


def clean_deadline_text(value):
    value = clean_text(value)

    if not value:
        return ""

    # Seldon bəzən deadline ilə yanaşı "Осталось 3 дня" yazısını da verir.
    value = re.sub(r"\s+Осталось\s+.*$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+Остался\s+.*$", "", value, flags=re.IGNORECASE)

    return clean_text(value)


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


def safe_inner_text_multiline(locator, timeout=5000):
    try:
        return clean_multiline_text(locator.inner_text(timeout=timeout))
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


def is_organizer_field_label(value):
    value = clean_text(value).lower()

    if not value:
        return False

    for label in ORGANIZER_FIELD_LABELS:
        label_lower = label.lower()

        if value == label_lower:
            return True

        if value.startswith(label_lower + ":"):
            return True

    return False


def strip_inline_label_value(line, label):
    line = clean_text(line)
    label = clean_text(label)

    if not line or not label:
        return ""

    lowered = line.lower()
    label_lower = label.lower()

    if lowered == label_lower:
        return ""

    if lowered.startswith(label_lower + ":"):
        return clean_text(line[len(label) + 1:])

    if lowered.startswith(label_lower + " "):
        return clean_text(line[len(label):])

    return ""


def next_non_label_value(lines, start_index, max_lookahead=10, organization_mode=False):
    for line in lines[start_index:start_index + max_lookahead]:
        value = clean_text(line)

        if not value:
            continue

        if is_masked_text(value):
            continue

        if is_organizer_field_label(value):
            continue

        for inline_label in [
            "Наименование",
            "ИНН",
            "Телефон",
            "Электронная почта",
            "Контактное лицо",
        ]:
            inline_value = strip_inline_label_value(value, inline_label)

            if inline_value:
                if organization_mode and inline_label == "Наименование":
                    org_value = normalize_organization_value(inline_value)

                    if org_value:
                        return org_value

                    continue

                if not organization_mode:
                    return inline_value

        if value.lower() in ["текущая", "коммерческая"]:
            continue

        if organization_mode:
            org_value = normalize_organization_value(value)

            if org_value:
                return org_value

            continue

        return value

    return ""


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


# -----------------------------------------------------------------------------
# Login
# -----------------------------------------------------------------------------


def is_seldon_login_page(page):
    try:
        current_url = page.url.lower()

        if "account.myseldon.com" in current_url:
            return True

        if page.locator("#Email").count() > 0:
            return True

    except Exception:
        pass

    return False


def body_looks_like_login_page(body_text):
    body_text = clean_text(body_text)

    if not body_text:
        return False

    login_markers = [
        "Электронная почта/Телефон",
        "Пароль",
        "Войти",
    ]

    return all(marker in body_text for marker in login_markers)


def ensure_seldon_login(page):
    if not SELDON_LOGIN or not SELDON_PASSWORD:
        print("[SELDON] Login məlumatları yoxdur: SELDON_LOGIN / SELDON_PASSWORD")
        return False

    print("[SELDON] Login yoxlanılır...")

    try:
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)

        try:
            page.wait_for_load_state("networkidle", timeout=25000)
        except Exception:
            pass

        page.wait_for_timeout(2000)
        close_possible_modals(page)

        if not is_seldon_login_page(page) and "win.myseldon.com" in page.url:
            print("[SELDON] Artıq login olunub.")
            return True

    except Exception as e:
        print("[SELDON] Login check zamanı xəta:", e)

    print("[SELDON] Login səhifəsi açılır...")

    try:
        page.goto(SELDON_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)

        page.wait_for_selector("#Email", timeout=30000)
        page.fill("#Email", SELDON_LOGIN)

        page.wait_for_selector("#Password", timeout=30000)
        page.fill("#Password", SELDON_PASSWORD)

        print("[SELDON] Login formu dolduruldu, Войти klik olunur...")

        try:
            page.get_by_role(
                "button",
                name=re.compile("Войти", re.IGNORECASE),
            ).click(timeout=10000)
        except Exception:
            page.locator(
                "button:has-text('Войти'), input[type='submit']"
            ).first.click(timeout=10000)

        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass

        page.wait_for_timeout(3000)

        print("[SELDON] Login sonrası URL:", page.url)

        if is_seldon_login_page(page):
            print("[SELDON] Login alınmadı: yenə login səhifəsindəyik.")
            return False

        if "win.myseldon.com" not in page.url:
            print("[SELDON] Login sonrası gözlənilən domain deyil:", page.url)
            return False

        print("[SELDON] Login uğurludur.")
        return True

    except Exception as e:
        print("[SELDON] Login error:", e)
        return False


# -----------------------------------------------------------------------------
# Grid filter and grid parsing
# -----------------------------------------------------------------------------


def apply_real_seldon_filter(page, keyword):
    print("[SELDON] Filter düyməsi axtarılır...")

    close_possible_modals(page)

    page.get_by_text("Фильтр", exact=True).click(timeout=30000)
    page.wait_for_selector('[data-testid="filter-modal"]', timeout=30000)

    print("[SELDON] Filter modal açıldı")

    subject_input = page.locator('[data-testid="filter-subject-or-input"]')
    fill_input(subject_input, keyword)

    print("[SELDON] Keyword yazıldı:", keyword)

    price_input = None

    price_input_selectors = [
        '[data-testid="filter-purchase-start-price-input-range-0"]',
        '[data-testid="filter-start-price-input-range-0"]',
    ]

    for selector in price_input_selectors:
        try:
            candidate = page.locator(selector).first
            candidate.wait_for(state="visible", timeout=5000)
            price_input = candidate
            print("[SELDON] Qiymət input selector tapıldı:", selector)
            break
        except Exception:
            continue

    if not price_input:
        raise Exception("Minimum qiymət input-u tapılmadı.")

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
                    return (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
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

                        const hasDates = /\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}/.test(rowText);
                        const hasPrice = /\d{1,3}(?:\s\d{3})+,\d{2}/.test(rowText);
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


# -----------------------------------------------------------------------------
# Detail parsing helpers
# -----------------------------------------------------------------------------


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

                    if is_masked_text(next_line):
                        continue

                    collected.append(next_line)

                    if len(" ".join(collected)) > 80:
                        break

                return clean_text(" ".join(collected))

            if lowered.startswith(label + ":"):
                value = clean_text(line.split(":", 1)[1])

                if is_masked_text(value):
                    return ""

                return value

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


def extract_organizer_from_body_text(body_text):
    result = {
        "organization": "",
        "organization_inn": "",
        "organization_phone": "",
        "organization_email": "",
        "contact_person": "",
    }

    lines = split_lines(body_text)

    if not lines:
        return result

    # 1. Detail blok:
    # Организатор
    # Наименование
    # АКЦИОНЕРНОЕ ОБЩЕСТВО ...
    # Регион
    # ...
    # ИНН
    # ...
    for index, line in enumerate(lines):
        if clean_text(line).lower() != "организатор":
            continue

        block_end = min(index + 100, len(lines))
        block = lines[index:block_end]

        if not any(clean_text(x).lower() == "наименование" for x in block):
            continue

        for i in range(index + 1, block_end):
            label = clean_text(lines[i]).lower()

            if label == "наименование" and not result["organization"]:
                result["organization"] = next_non_label_value(
                    lines,
                    i + 1,
                    max_lookahead=10,
                    organization_mode=True,
                )

            elif label == "инн" and not result["organization_inn"]:
                inn = next_non_label_value(lines, i + 1, max_lookahead=5)

                if re.search(r"\d{10,12}", inn):
                    result["organization_inn"] = re.search(r"\d{10,12}", inn).group(0)

            elif label == "телефон" and not result["organization_phone"]:
                result["organization_phone"] = next_non_label_value(lines, i + 1, max_lookahead=5)

            elif label == "электронная почта" and not result["organization_email"]:
                result["organization_email"] = next_non_label_value(lines, i + 1, max_lookahead=5)

            elif label == "контактное лицо" and not result["contact_person"]:
                result["contact_person"] = next_non_label_value(lines, i + 1, max_lookahead=5)

        if result["organization"] or result["organization_inn"]:
            break

    # 2. Header fallback:
    # Начальная цена
    # 499 000,00 RUB
    # Организатор
    # АКЦИОНЕРНОЕ ОБЩЕСТВО ...
    # Источник
    if not result["organization"]:
        for index, line in enumerate(lines):
            if clean_text(line).lower() == "организатор":
                candidate = next_non_label_value(
                    lines,
                    index + 1,
                    max_lookahead=12,
                    organization_mode=True,
                )

                if candidate:
                    result["organization"] = candidate
                    break

    # 3. Ümumi INN fallback
    if not result["organization_inn"]:
        for index, line in enumerate(lines):
            if clean_text(line).lower() == "инн":
                inn = next_non_label_value(lines, index + 1, max_lookahead=5)

                if re.search(r"\d{10,12}", inn):
                    result["organization_inn"] = re.search(r"\d{10,12}", inn).group(0)
                    break

    for key in list(result.keys()):
        result[key] = clear_if_masked(result[key])

    result["organization"] = normalize_organization_value(result.get("organization"))

    return result


def merge_organizer_data(primary, fallback):
    result = dict(primary or {})

    for key, value in (fallback or {}).items():
        current = clear_if_masked(result.get(key))
        new_value = clear_if_masked(value)

        if key == "organization":
            current = normalize_organization_value(current)
            new_value = normalize_organization_value(new_value)

        if not current and new_value:
            result[key] = new_value
        else:
            result[key] = current

    return result


def extract_organizer_from_detail_page(detail_page, body_text=""):
    """
    Organizer-i Seldon detail-dəki real company blokundan götürür.

    Əsas hədəflər:
    1. basis.myseldon.com/ru/company linkinin mətni
    2. div[role="table"] daxilində row/cell strukturu:
       Наименование -> organization
       ИНН -> organization_inn
       Регион -> ignore
    3. body text fallback
    """
    result = {
        "organization": "",
        "organization_inn": "",
        "organization_phone": "",
        "organization_email": "",
        "contact_person": "",
    }

    try:
        # Customer/company bloku səhifənin aşağı hissəsində render oluna bilər.
        try:
            detail_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            detail_page.wait_for_timeout(2500)
        except Exception:
            pass

        try:
            detail_page.wait_for_selector(
                "a[href*='basis.myseldon.com/ru/company'], div[role='table'] div[role='row']",
                timeout=12000,
            )
        except Exception:
            pass

        js_data = detail_page.evaluate(
            """
            () => {
                function normalize(value) {
                    return (value || '')
                        .replace(/\u00a0/g, ' ')
                        .replace(/\s+/g, ' ')
                        .trim();
                }

                function isMasked(value) {
                    value = normalize(value);

                    if (!value) return false;

                    const chars = ['▒', '█', '■', '*', '•'];
                    let count = 0;

                    for (const ch of chars) {
                        count += value.split(ch).length - 1;
                    }

                    return count >= 5 && count / Math.max(value.length, 1) > 0.3;
                }

                function isRegionValue(value) {
                    value = normalize(value).toLowerCase();

                    if (!value) return false;

                    if (/\b\d{1,3}\s*регион\b/.test(value)) {
                        return true;
                    }

                    const regionWords = [
                        'область',
                        'край',
                        'республика',
                        'автономный округ',
                        'город',
                        'район',
                        'регион',
                        'москва',
                        'санкт-петербург',
                        'севастополь'
                    ];

                    return regionWords.some(word => value.includes(word));
                }

                function looksLikeOrganization(value) {
                    value = normalize(value);

                    if (!value) return false;
                    if (isMasked(value)) return false;
                    if (isRegionValue(value)) return false;

                    const lower = value.toLowerCase();

                    const markers = [
                        'акционерное общество',
                        'ао ',
                        ' ао',
                        'общество с ограниченной ответственностью',
                        'ооо ',
                        ' ооо',
                        'публичное акционерное общество',
                        'пао ',
                        ' пао',
                        'муниципальное',
                        'государственное',
                        'федеральное',
                        'казенное',
                        'бюджетное',
                        'автономное',
                        'учреждение',
                        'предприятие',
                        'компания'
                    ];

                    if (markers.some(marker => lower.includes(marker))) {
                        return true;
                    }

                    if (value.length > 10 && value.toUpperCase() === value) {
                        return true;
                    }

                    return false;
                }

                function getText(el) {
                    if (!el) return '';
                    return normalize(el.innerText || el.textContent || '');
                }

                function getCellText(row, index) {
                    const cells = Array.from(row.querySelectorAll('[role="cell"]'));

                    if (!cells[index]) return '';

                    return getText(cells[index]);
                }

                function findNearestTable(el) {
                    let current = el;

                    for (let i = 0; i < 10 && current; i++) {
                        if (
                            current.getAttribute &&
                            current.getAttribute('role') === 'table'
                        ) {
                            return current;
                        }

                        current = current.parentElement;
                    }

                    return null;
                }

                function readRowsFromTable(table) {
                    const output = {
                        organization: '',
                        organization_inn: '',
                        organization_phone: '',
                        organization_email: '',
                        contact_person: ''
                    };

                    if (!table) return output;

                    const rows = Array.from(table.querySelectorAll('[role="row"]'));

                    for (const row of rows) {
                        const label = getCellText(row, 0);
                        const value = getCellText(row, 1);

                        if (!label || !value) continue;
                        if (isMasked(value)) continue;

                        if (label === 'Наименование') {
                            if (looksLikeOrganization(value)) {
                                output.organization = value;
                            }
                        }

                        if (label === 'ИНН') {
                            const innMatch = value.match(/\d{10,12}/);

                            if (innMatch) {
                                output.organization_inn = innMatch[0];
                            }
                        }

                        if (label === 'Телефон') {
                            output.organization_phone = value;
                        }

                        if (label === 'Электронная почта') {
                            output.organization_email = value;
                        }

                        if (label === 'Контактное лицо') {
                            output.contact_person = value;
                        }

                        // Регион qəsdən oxunmur.
                    }

                    return output;
                }

                function merge(base, extra) {
                    for (const key of Object.keys(base)) {
                        if (!base[key] && extra[key]) {
                            base[key] = extra[key];
                        }
                    }

                    return base;
                }

                const result = {
                    organization: '',
                    organization_inn: '',
                    organization_phone: '',
                    organization_email: '',
                    contact_person: '',
                    method: '',
                    debugBasisLinks: 0,
                    debugTables: 0,
                    debugRows: 0,
                    debugFirstTables: []
                };

                // 1. Ən stabil mənbə: Seldon Basis company linki.
                const basisLinks = Array.from(
                    document.querySelectorAll('a[href*="basis.myseldon.com/ru/company"]')
                );

                result.debugBasisLinks = basisLinks.length;

                for (const link of basisLinks) {
                    const value = getText(link);

                    if (looksLikeOrganization(value)) {
                        result.organization = value;
                        result.method = 'basis_company_link';

                        const table = findNearestTable(link);
                        result.debugRows = table ? table.querySelectorAll('[role="row"]').length : 0;
                        merge(result, readRowsFromTable(table));

                        return result;
                    }
                }

                // 2. Verilən HTML: cardCustomer_infoGrid / infoGrid table.
                const tables = Array.from(document.querySelectorAll('[role="table"]'));
                result.debugTables = tables.length;

                for (let tableIndex = 0; tableIndex < tables.length; tableIndex++) {
                    const table = tables[tableIndex];
                    const tableClass = table.getAttribute('class') || '';
                    const tableText = getText(table);

                    if (result.debugFirstTables.length < 5) {
                        result.debugFirstTables.push({
                            index: tableIndex,
                            className: tableClass,
                            text: tableText.slice(0, 300)
                        });
                    }

                    const isLikelyCustomerTable =
                        tableClass.includes('cardCustomer_infoGrid') ||
                        tableClass.includes('infoGrid') ||
                        (
                            tableText.includes('Наименование') &&
                            (
                                tableText.includes('ИНН') ||
                                tableText.includes('Регион') ||
                                tableText.includes('Телефон') ||
                                tableText.includes('Электронная почта')
                            )
                        );

                    if (!isLikelyCustomerTable) {
                        continue;
                    }

                    const tableResult = readRowsFromTable(table);

                    if (tableResult.organization || tableResult.organization_inn) {
                        merge(result, tableResult);
                        result.method = tableClass.includes('cardCustomer_infoGrid')
                            ? 'cardCustomer_infoGrid'
                            : 'generic_role_table';
                        result.debugRows = table.querySelectorAll('[role="row"]').length;

                        return result;
                    }
                }

                // 3. Son DOM fallback: bütün row-ları gəz.
                const rows = Array.from(document.querySelectorAll('[role="row"]'));
                result.debugRows = rows.length;

                for (const row of rows) {
                    const label = getCellText(row, 0);
                    const value = getCellText(row, 1);

                    if (!label || !value) continue;
                    if (isMasked(value)) continue;

                    if (label === 'Наименование' && looksLikeOrganization(value)) {
                        result.organization = value;
                        result.method = 'global_role_row';
                    }

                    if (label === 'ИНН') {
                        const innMatch = value.match(/\d{10,12}/);

                        if (innMatch && !result.organization_inn) {
                            result.organization_inn = innMatch[0];
                        }
                    }

                    if (result.organization && result.organization_inn) {
                        return result;
                    }
                }

                return result;
            }
            """
        )

        if js_data:
            print("[SELDON] Organizer DOM method:", clean_text(js_data.get("method")))
            print("[SELDON] Organizer DOM basis links:", js_data.get("debugBasisLinks"))
            print("[SELDON] Organizer DOM tables:", js_data.get("debugTables"))
            print("[SELDON] Organizer DOM rows:", js_data.get("debugRows"))
            print("[SELDON] Organizer DOM organization:", repr(clean_text(js_data.get("organization"))))
            print("[SELDON] Organizer DOM INN:", repr(clean_text(js_data.get("organization_inn"))))

            if DEBUG_SELDON:
                print("[SELDON] Organizer DOM first tables:", repr(js_data.get("debugFirstTables")))

            result = {
                "organization": normalize_organization_value(js_data.get("organization")),
                "organization_inn": clear_if_masked(js_data.get("organization_inn")),
                "organization_phone": clear_if_masked(js_data.get("organization_phone")),
                "organization_email": clear_if_masked(js_data.get("organization_email")),
                "contact_person": clear_if_masked(js_data.get("contact_person")),
            }

    except Exception as e:
        print("[SELDON] Organizer DOM parse error:", e)

    # 4. Body text fallback.
    if not result.get("organization") or not result.get("organization_inn"):
        body_result = extract_organizer_from_body_text(body_text)
        body_result["organization"] = normalize_organization_value(
            body_result.get("organization")
        )
        result = merge_organizer_data(result, body_result)

    for key in list(result.keys()):
        result[key] = clear_if_masked(result[key])

    result["organization"] = normalize_organization_value(result.get("organization"))

    print("[SELDON] Organizer final organization:", repr(result.get("organization")))
    print("[SELDON] Organizer final INN:", repr(result.get("organization_inn")))

    return result

def extract_price_from_detail_page(detail_page):
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
                .replace(/\u00a0/g, ' ')
                .replace(/\s+/g, ' ')
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
                /\d{1,3}(?:\s\d{3})+(?:[,.]\d{1,2})?\s*(?:RUB|руб\.?|₽)?|\d{6,}(?:[,.]\d{1,2})?\s*(?:RUB|руб\.?|₽)?/i
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

                const ownPrice = extractPriceAfterLabel(nodeText, label);

                if (ownPrice) {
                    return {
                        priceText: ownPrice,
                        sourceText: nodeText,
                        method: 'own_text_after_label'
                    };
                }

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
    body_text_before = safe_inner_text_multiline(detail_page.locator("body").first, timeout=10000)

    try:
        detail_page.get_by_text("Полное наименование", exact=False).first.click(
            timeout=7000,
            force=True
        )
        detail_page.wait_for_timeout(1200)
        print("[SELDON] Полное наименование force klikləndi.")
    except Exception as e:
        print(f"[SELDON] Полное наименование klik alınmadı, fallback istifadə olunur: {e}")

    body_text = safe_inner_text_multiline(detail_page.locator("body").first, timeout=10000)

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


def debug_detail_page(detail_page, detail_url, tender_id="unknown"):
    if not DEBUG_SELDON:
        return

    try:
        os.makedirs("logs", exist_ok=True)

        safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(tender_id or "unknown"))

        detail_page.screenshot(
            path=f"logs/seldon_detail_debug_{safe_id}.png",
            full_page=True
        )

        body_text = safe_inner_text_multiline(detail_page.locator("body").first, timeout=10000)

        print("=" * 80)
        print("[SELDON][DEBUG][DETAIL URL]", detail_url)
        print("[SELDON][DEBUG][CURRENT URL]", detail_page.url)
        print("[SELDON][DEBUG][LOGIN PAGE]", is_seldon_login_page(detail_page))
        print("[SELDON][DEBUG][BODY LOOKS LOGIN]", body_looks_like_login_page(body_text))
        print("[SELDON][DEBUG][HAS MASKED TEXT]", "▒" in body_text)
        print("[SELDON][DEBUG][BODY START]", repr(body_text[:3000]))
        print("=" * 80)

    except Exception as e:
        print("[SELDON][DEBUG] detail debug error:", e)


# -----------------------------------------------------------------------------
# Detail parser
# -----------------------------------------------------------------------------


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

        body_text = safe_inner_text_multiline(detail_page.locator("body").first, timeout=15000)

        if is_seldon_login_page(detail_page) or body_looks_like_login_page(body_text):
            print("[SELDON] Detail səhifədə login göründü. Təkrar login ediləcək:", detail_url)

            if not ensure_seldon_login(detail_page):
                print("[SELDON] Detail üçün login alınmadı:", detail_url)
                return None

            detail_page.goto(detail_url, wait_until="networkidle", timeout=60000)
            detail_page.wait_for_timeout(3000)
            body_text = safe_inner_text_multiline(detail_page.locator("body").first, timeout=15000)

        debug_detail_page(detail_page, detail_url, tender_id=detail_url.rstrip("/").split("/")[-2])

        if not body_text:
            print("[SELDON] Detail body boşdur:", detail_url)
            return None

        title = get_title_from_detail_page(detail_page)

        body_text_after_title = safe_inner_text_multiline(detail_page.locator("body").first, timeout=15000)

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
                "Окончание приёма заявок",
                "Окончание подачи заявок",
                "Дата окончания подачи заявок",
                "Срок подачи заявок",
            ]
        )

        if not deadline:
            deadline = grid_deadline
            print("[SELDON] Son tarix grid-dən götürüldü:", deadline)

        deadline = clean_deadline_text(deadline)
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

        organizer_data = extract_organizer_from_detail_page(detail_page, body_text=body_text)

        organization = normalize_organization_value(organizer_data.get("organization"))

        if not organization:
            fallback_organization = extract_value_after_label_by_lines(
                body_text,
                [
                    "Организатор",
                    "Заказчик",
                    "Наименование заказчика",
                    "Покупатель",
                ],
                stop_labels=[
                    "Источник",
                    "Начальная цена",
                    "НМЦК",
                    "Статус",
                    "Осталось дней",
                    "Начало приема",
                    "Окончание приема",
                    "Способ закупки",
                    "Тип закупки",
                    "Регион",
                    "ИНН",
                    "E-mail",
                    "ЭТП",
                    "Ссылка",
                    "Общие сведения",
                    "Лоты",
                    "Документы",
                ]
            )

            organization = normalize_organization_value(fallback_organization)

        if not organization:
            body_organizer_data = extract_organizer_from_body_text(body_text)
            body_organizer_data["organization"] = normalize_organization_value(
                body_organizer_data.get("organization")
            )
            organization = body_organizer_data.get("organization")
            organizer_data = merge_organizer_data(organizer_data, body_organizer_data)

        organization = normalize_organization_value(organization)

        if not organization:
            title_organization = normalize_organization_value(
                extract_organization_from_title(title)
            )

            if title_organization:
                print("[SELDON] Organization title fallback-dan götürüldü:", repr(title_organization))
                organization = title_organization

        organization_display = organization or "Yoxdur"

        organization_inn = clear_if_masked(organizer_data.get("organization_inn")) or "Yoxdur"
        organization_phone = clear_if_masked(organizer_data.get("organization_phone")) or "Yoxdur"
        organization_email = clear_if_masked(organizer_data.get("organization_email")) or "Yoxdur"
        contact_person = clear_if_masked(organizer_data.get("contact_person")) or "Yoxdur"

        print("[SELDON] FINAL organization:", repr(organization_display))
        print("[SELDON] FINAL organization_inn:", repr(organization_inn))
        print("[SELDON] FINAL url:", detail_url)

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
            "organization": organization_display,
            "organization_inn": organization_inn,
            "organization_phone": organization_phone,
            "organization_email": organization_email,
            "contact_person": contact_person,
            "customer": organization_display,
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


# -----------------------------------------------------------------------------
# Main source function
# -----------------------------------------------------------------------------


def search_seldon(page, keyword):
    results = []

    print("[SELDON] Başladı")
    print("[SELDON] Keyword:", keyword)
    print("[SELDON] Grid URL:", SELDON_GRID_URL)

    if not ensure_seldon_login(page):
        print("[SELDON] Login alınmadığı üçün source dayandırıldı.")
        return results

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
                print("[SELDON] Login səhifəsi göründü. Yenidən login yoxlanılır...")

                if not ensure_seldon_login(page):
                    print("[SELDON] Təkrar login alınmadı.")
                    return results

                page.goto(grid_url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(5000)
                close_possible_modals(page)

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
                print("Təşkilat:", tender.get("organization"))

                if len(results) >= SELDON_MAX_ITEMS_PER_KEYWORD:
                    print("[SELDON] Limit doldu.")
                    return results

            time.sleep(1)

    except Exception as e:
        print(f"[SELDON] Search error: {e}")

    print("[SELDON] Bitdi. Tapılan tender sayı:", len(results))

    return results
