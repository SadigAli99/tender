from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class TenderTitleLink:
    text: str
    url: str


@dataclass
class TenderResult:
    source: str
    keyword: str
    title: str
    url: str

    organization: Optional[str] = None
    price: Optional[str] = None
    tender_type: Optional[str] = None
    status: Optional[str] = None
    deadline: Optional[str] = None
    publish_date: Optional[str] = None

    review_end_date: Optional[str] = None
    documents: List[str] = field(default_factory=list)
    title_links: List[TenderTitleLink] = field(default_factory=list)

    def to_dict(self):
        data = asdict(self)

        data["title_links"] = [
            {
                "text": item.text,
                "url": item.url,
            }
            for item in self.title_links
        ]

        return data
