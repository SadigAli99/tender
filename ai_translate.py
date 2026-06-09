import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2-mini")


def translate_tender_to_az(tender: dict) -> dict:
    """
    Tender məlumatlarını Azərbaycan dilinə tərcümə edir.
    Qiymət, tarix, tender_id və link dəyişdirilmir.
    """

    payload = {
        "title": tender.get("title"),
        "organization": tender.get("organization"),
        "price_text": tender.get("price_text"),
        "price_rub": tender.get("price_rub"),
        "deadline_text": tender.get("deadline_text"),
        "publish_date_text": tender.get("publish_date_text"),
        "tender_type": tender.get("tender_type"),
        "status": tender.get("status"),
        "source": tender.get("source"),
        "tender_url": tender.get("tender_url"),
        "tender_id": tender.get("tender_id"),
    }

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "system",
                "content": (
                    "Sən tender məlumatlarını rus dilindən Azərbaycan dilinə tərcümə edirsən. "
                    "Yalnız mətnləri tərcümə et. Qiymət, tarix, rəqəm, link, tender_id və valyutanı dəyişmə. "
                    "Cavabı yalnız JSON formatında qaytar."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "translated_tender",
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "organization": {"type": "string"},
                        "price_text": {"type": "string"},
                        "deadline_text": {"type": "string"},
                        "publish_date_text": {"type": "string"},
                        "tender_type": {"type": "string"},
                        "status": {"type": "string"},
                    },
                    "required": [
                        "title",
                        "organization",
                        "price_text",
                        "deadline_text",
                        "publish_date_text",
                        "tender_type",
                        "status",
                    ],
                    "additionalProperties": False,
                },
            }
        },
    )

    translated = json.loads(response.output_text)

    return {
        **tender,
        "translated_title": translated.get("title") or tender.get("title"),
        "translated_organization": translated.get("organization")
        or tender.get("organization"),
        "translated_price_text": translated.get("price_text")
        or tender.get("price_text"),
        "translated_deadline_text": translated.get("deadline_text")
        or tender.get("deadline_text"),
        "translated_publish_date_text": translated.get("publish_date_text")
        or tender.get("publish_date_text"),
        "translated_tender_type": translated.get("tender_type")
        or tender.get("tender_type"),
        "translated_status": translated.get("status") or tender.get("status"),
    }
