import re
from urllib.parse import urljoin


def clean_text(value):
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def find_value_after(lines, label):
    for index, line in enumerate(lines):
        if line.strip() == label:
            if index + 1 < len(lines):
                return clean_text(lines[index + 1])

    return None


def find_value_after_contains(lines, labels):
    for index, line in enumerate(lines):
        line_lower = line.lower()

        for label in labels:
            if label.lower() in line_lower:
                if index + 1 < len(lines):
                    value = clean_text(lines[index + 1])

                    if value:
                        return value

    return None


def is_bad_value(value):
    if not value:
        return True

    value_lower = str(value).lower()

    bad_words = [
        "доступно после регистрации",
        "зарегистрируйтесь",
        "войдите",
        "политика обработки",
        "персональных данных",
        "пользовательское соглашение",
        "cookie",
        "помощь",
        "поддержка",
    ]

    return any(word in value_lower for word in bad_words)


def get_document_names(lines):
    documents = []
    inside_documents = False

    for line in lines:
        if line == "Документы":
            inside_documents = True
            continue

        if inside_documents and line == "Еще могут подойти закупки":
            break

        if inside_documents:
            lower_line = line.lower()

            is_file = (
                ".doc" in lower_line or
                ".docx" in lower_line or
                ".xls" in lower_line or
                ".xlsx" in lower_line or
                ".pdf" in lower_line or
                ".zip" in lower_line or
                ".rar" in lower_line or
                ".7z" in lower_line
            )

            if is_file and "░" not in line:
                documents.append(line)

    return documents


def extract_documents_from_links(page):
    documents = []

    try:
        links = page.locator("a[href]").all()

        for link in links:
            href = link.get_attribute("href") or ""
            text = clean_text(link.inner_text())

            href_lower = href.lower()
            text_lower = text.lower()

            is_document = (
                ".doc" in href_lower or
                ".docx" in href_lower or
                ".xls" in href_lower or
                ".xlsx" in href_lower or
                ".pdf" in href_lower or
                ".zip" in href_lower or
                ".rar" in href_lower or
                ".7z" in href_lower or
                "download" in href_lower or
                "file" in href_lower or
                "document" in href_lower or
                "документ" in text_lower or
                "документация" in text_lower or
                "скачать" in text_lower
            )

            if not is_document:
                continue

            if not text:
                text = href

            if text not in documents:
                documents.append(text)

    except Exception:
        pass

    return documents[:10]


def extract_title_links(page, title):
    title_links = []

    if not title:
        return title_links

    try:
        links = page.locator("a[href]").all()

        for link in links:
            href = link.get_attribute("href") or ""
            text = clean_text(link.inner_text())

            if not href or not text:
                continue

            if text in title and "." in text:
                title_links.append({
                    "text": text,
                    "url": urljoin(page.url, href)
                })

    except Exception:
        pass

    unique_links = []
    seen = set()

    for item in title_links:
        key = (item["text"], item["url"])

        if key in seen:
            continue

        seen.add(key)
        unique_links.append(item)

    return unique_links


def parse_date_from_text(text):
    if not text:
        return None

    text = str(text)

    match_full_year = re.search(
        r"(\d{2})\.(\d{2})\.(\d{4})(?:\s+\d{1,2}:\d{2})?(?:\s*\(?мск\)?)?",
        text,
        re.IGNORECASE
    )

    if match_full_year:
        day, month, year = match_full_year.groups()
        matched_text = clean_text(match_full_year.group(0))

        if ":" in matched_text:
            return matched_text

        return f"{day}.{month}.{year}"

    match_short_year = re.search(
        r"(\d{2})\.(\d{2})\.(\d{2})",
        text
    )

    if match_short_year:
        day, month, short_year = match_short_year.groups()
        year = f"20{short_year}"

        return f"{day}.{month}.{year}"

    return None


def parse_price_from_text(text):
    if not text:
        return None

    patterns = [
        r"(?:Начальная цена контракта|Начальная цена|Начальная максимальная цена|Цена контракта|Стоимость|Бюджет)[^\d]{0,100}([\d\s]+(?:[,.]\d{1,2})?\s*(?:₽|руб\.?|рублей))",
        r"([\d\s]+(?:[,.]\d{1,2})?\s*₽)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return clean_text(match.group(1))

    return None


def parse_status_from_lines(lines):
    statuses = [
        "Этап подачи заявок",
        "Прием заявок",
        "Приём заявок",
        "Подача заявок",
        "Работа комиссии",
        "Рассмотрение заявок",
        "Подведение итогов",
        "Завершен",
        "Завершён",
        "Отменен",
        "Отменён",
        "Архив",
    ]

    for line in lines:
        for status in statuses:
            if status.lower() in line.lower():
                return status

    return None


def parse_purchase_type_from_text(text):
    if not text:
        return None

    types = [
        "44-ФЗ",
        "223-ФЗ",
        "615-ПП",
        "Коммерческие",
        "Коммерческий",
        "Электронный аукцион",
        "Аукцион",
        "Открытый конкурс",
        "Конкурс",
        "Запрос котировок",
        "Запрос предложений",
        "Квалификационный отбор",
        "Закупка у единственного поставщика",
    ]

    found = []
    text_lower = text.lower()

    for item in types:
        if item.lower() in text_lower:
            found.append(item)

    if found:
        return ", ".join(found[:3])

    return None


def parse_title(page, fallback_title):
    try:
        h1 = page.locator("h1").first

        if h1.count() > 0:
            title = clean_text(h1.inner_text())

            if title:
                title = re.sub(r"^Тендер:\s*", "", title, flags=re.IGNORECASE)
                return title
    except Exception:
        pass

    if fallback_title:
        fallback_title = re.sub(
            r"^Тендер:\s*",
            "",
            fallback_title,
            flags=re.IGNORECASE
        )

    return fallback_title


def parse_organization(lines):
    labels = [
        "Заказчик",
        "Организатор",
        "Покупатель",
        "Наименование заказчика",
        "Полное наименование заказчика",
    ]

    for index, line in enumerate(lines):
        line_lower = line.lower()

        for label in labels:
            label_lower = label.lower()

            if label_lower == line_lower:
                if index + 1 < len(lines):
                    value = clean_text(lines[index + 1])

                    if not is_bad_value(value):
                        return value

            if label_lower in line_lower:
                value = re.sub(label, "", line, flags=re.IGNORECASE)
                value = value.replace(":", "").strip()
                value = clean_text(value)

                if value and not is_bad_value(value):
                    return value

    return None


def parse_rostender_publish_date(lines):
    full_text = "\n".join(lines)

    match = re.search(
        r"Тендер\s*№\s*\d+\s*от\s*(\d{2}\.\d{2}\.\d{2,4})",
        full_text,
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        return None

    raw_date = match.group(1)
    parts = raw_date.split(".")

    if len(parts) != 3:
        return None

    day, month, year = parts

    if len(year) == 2:
        year = f"20{year}"

    return f"{day}.{month}.{year}"


def parse_kontur_publish_date(lines):
    top_lines = lines[:80]

    publish_words = [
        "опубликован",
        "опубликовано",
        "опубликована",
        "размещено",
        "размещена",
        "дата публикации",
        "дата размещения",
    ]

    for line in top_lines:
        line_lower = line.lower()

        if any(word in line_lower for word in publish_words):
            parsed = parse_date_from_text(line)

            if parsed:
                return parsed

    return None


def parse_publish_date(lines, source=None):
    if source == "rostender.info":
        return parse_rostender_publish_date(lines)

    if source == "zakupki.kontur.ru":
        return parse_kontur_publish_date(lines)

    return None


def normalize_common_fields(tender):
    tender["organization"] = (
        tender.get("organization")
        or tender.get("customer")
        or tender.get("company")
    )

    if tender.get("organization") and is_bad_value(tender.get("organization")):
        tender["organization"] = None

    tender["tender_type"] = (
        tender.get("tender_type")
        or tender.get("purchase_type")
        or tender.get("type")
    )

    tender["deadline"] = (
        tender.get("deadline")
        or tender.get("application_end")
    )

    tender["publish_date"] = (
        tender.get("publish_date")
        or tender.get("published_at")
        or tender.get("date")
    )

    if tender.get("publish_date") and is_bad_value(tender.get("publish_date")):
        tender["publish_date"] = None

    if "documents" not in tender or tender["documents"] is None:
        tender["documents"] = []

    if "title_links" not in tender or tender["title_links"] is None:
        tender["title_links"] = []

    return tender


def parse_zakupki_kontur_detail(page, tender):
    page.goto(tender["url"], wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)

    body_text = page.locator("body").inner_text()

    lines = []

    for line in body_text.splitlines():
        clean_line = line.strip()

        if clean_line:
            lines.append(clean_line)

    full_text = "\n".join(lines)

    title = parse_title(page, tender.get("title"))
    status = None
    deadline = None

    for index, line in enumerate(lines):
        if line == "Этап подачи заявок":
            status = line

            if index + 1 < len(lines):
                deadline = lines[index + 1].replace("до ", "").strip()

            break

    organization = parse_organization(lines)

    price = (
        find_value_after(lines, "Начальная цена контракта")
        or find_value_after(lines, "Начальная цена")
        or parse_price_from_text(full_text)
    )

    purchase_type = (
        find_value_after(lines, "Тип закупки")
        or parse_purchase_type_from_text(full_text)
    )

    application_end = (
        find_value_after(lines, "Окончание подачи заявок")
        or deadline
    )

    review_end = find_value_after(lines, "Окончание рассмотрения заявок")
    publish_date = parse_publish_date(lines, "zakupki.kontur.ru")
    documents = get_document_names(lines)

    if not documents:
        documents = extract_documents_from_links(page)

    if title:
        tender["title"] = title

    if organization:
        tender["organization"] = organization

    if status:
        tender["status"] = status

    if deadline:
        tender["deadline"] = deadline

    if price:
        tender["price"] = price

    if purchase_type:
        tender["purchase_type"] = purchase_type
        tender["tender_type"] = purchase_type

    if application_end:
        tender["application_end"] = application_end
        tender["deadline"] = application_end

    if review_end:
        tender["review_end"] = review_end
        tender["review_end_date"] = review_end

    if publish_date:
        tender["publish_date"] = publish_date

    if documents:
        tender["documents"] = documents

    tender["title_links"] = extract_title_links(page, tender.get("title"))

    return normalize_common_fields(tender)


def parse_rostender_detail(page, tender):
    url = tender.get("url")

    if not url:
        return normalize_common_fields(tender)

    print("[ROSTENDER DETAIL] Parse:", url)

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)

        body_text = page.locator("body").inner_text()

        lines = []

        for line in body_text.splitlines():
            clean_line = line.strip()

            if clean_line:
                lines.append(clean_line)

        full_text = "\n".join(lines)

        title = parse_title(page, tender.get("title"))
        status = parse_status_from_lines(lines)
        organization = parse_organization(lines)

        price = (
            find_value_after(lines, "Начальная цена")
            or find_value_after(lines, "Начальная цена контракта")
            or find_value_after(lines, "Цена контракта")
            or parse_price_from_text(full_text)
        )

        purchase_type = (
            find_value_after(lines, "Тип закупки")
            or find_value_after(lines, "Способ закупки")
            or parse_purchase_type_from_text(full_text)
        )

        application_end = (
            find_value_after(lines, "Окончание подачи заявок")
            or find_value_after(lines, "Дата окончания подачи заявок")
            or find_value_after(lines, "Прием заявок до")
            or find_value_after(lines, "Приём заявок до")
        )

        review_end = (
            find_value_after(lines, "Окончание рассмотрения заявок")
            or find_value_after(lines, "Дата рассмотрения заявок")
            or find_value_after(lines, "Подведение итогов")
            or find_value_after(lines, "Дата подведения итогов")
        )

        publish_date = parse_publish_date(lines, "rostender.info")

        if not application_end:
            for index, line in enumerate(lines):
                line_lower = line.lower()

                if (
                    "окончание подачи заявок" in line_lower
                    or "прием заявок до" in line_lower
                    or "приём заявок до" in line_lower
                    or "подача заявок до" in line_lower
                    or "окончание" in line_lower
                ):
                    application_end = parse_date_from_text(line)

                    if not application_end and index + 1 < len(lines):
                        application_end = parse_date_from_text(lines[index + 1])

                    break

        if not review_end:
            for index, line in enumerate(lines):
                line_lower = line.lower()

                if (
                    "окончание рассмотрения заявок" in line_lower
                    or "рассмотрение заявок" in line_lower
                    or "подведение итогов" in line_lower
                ):
                    review_end = parse_date_from_text(line)

                    if not review_end and index + 1 < len(lines):
                        review_end = parse_date_from_text(lines[index + 1])

                    break

        if not application_end:
            application_end = find_value_after_contains(lines, [
                "Окончание",
                "Заканчивается",
                "Завершение"
            ])

        if title:
            tender["title"] = title

        if organization:
            tender["organization"] = organization

        if status:
            tender["status"] = status

        if application_end:
            tender["application_end"] = application_end
            tender["deadline"] = application_end

        if price:
            tender["price"] = price

        if purchase_type:
            tender["purchase_type"] = purchase_type
            tender["tender_type"] = purchase_type

        if review_end:
            tender["review_end"] = review_end
            tender["review_end_date"] = review_end

        if publish_date:
            tender["publish_date"] = publish_date

        documents = get_document_names(lines)

        if not documents:
            documents = extract_documents_from_links(page)

        if documents:
            tender["documents"] = documents

        tender["title_links"] = extract_title_links(page, tender.get("title"))

        return normalize_common_fields(tender)

    except Exception as e:
        print(f"[ROSTENDER DETAIL ERROR] {url} | {e}")
        return normalize_common_fields(tender)


def parse_tender_detail(page, tender):
    source = tender.get("source")

    if source == "zakupki.kontur.ru":
        return parse_zakupki_kontur_detail(page, tender)

    if source == "rostender.info":
        return parse_rostender_detail(page, tender)

    return normalize_common_fields(tender)
