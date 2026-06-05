from sources.kontur import search_kontur
from sources.rostender import search_rostender


ACTIVE_SOURCES = [
    {
        "name": "zakupki.kontur.ru",
        "search_func": search_kontur,
    },
    {
        "name": "rostender.info",
        "search_func": search_rostender,
    },
]
