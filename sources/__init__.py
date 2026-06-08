from sources.kontur import search_kontur
from sources.rostender import search_rostender
from sources.seldon import search_seldon


ACTIVE_SOURCES = [
    {
        "name": "zakupki.kontur.ru",
        "search_func": search_kontur,
    },
    {
        "name": "rostender.info",
        "search_func": search_rostender,
    },
    {
        "name" : "win.myseldon.com",
        "search_func" : search_seldon
    }
]
