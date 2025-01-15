from itertools import zip_longest
from math import ceil
import time

from discord import Embed

ARTICLES = {"the", "a", "an"}
CONJ = {"for", "and", "nor", "but", "or", "yet", "so"}
PREP = {"of", "to", "for", "in"}
ALL_CAPS = {"cs", "ms"}
NO_CAPS = ARTICLES.union(CONJ).union(PREP)
SPECIAL_CAPS = {"phd": "PhD"}

ZERO_WIDTH = "\u200b"
PITT_ROYAL = 0x003594
PITT_GOLD = 0xFFB81C


def titlecase(string: str) -> str:
    words = []
    for i, word in enumerate(string.lower().split()):
        if word in ALL_CAPS:
            words.append(word.upper())
        elif word in SPECIAL_CAPS:
            words.append(SPECIAL_CAPS[word])
        elif i != 0 and word in NO_CAPS:
            words.append(word)
        else:
            words.append(word.title())
    return " ".join(words)


def reformat_time_str(time_str: str) -> str:
    to_time_struct = time.strptime(time_str, "%H.%M.%S.%f")
    return time.strftime("%-I:%M%p", to_time_struct)


def to_column_embeds(entries: list[tuple[str, str]], title: str, per_page: int = 12) -> list[Embed]:
    col_embeds: list[Embed] = []
    total_pages = ceil(len(entries) / per_page)

    # https://docs.python.org/3/library/itertools.html#itertools-recipes
    entry_groups = zip_longest(*[iter(entries)] * per_page, fillvalue=(None, None))
    for i, page_entries in enumerate(entry_groups, start=1):
        page = Embed(title=title, color=PITT_ROYAL if i % 2 else PITT_GOLD)
        for heading, desc in page_entries:
            if heading and desc:
                page.add_field(name=heading, value=desc)
            else:  # Empty fields serve as placeholders for alignment
                page.add_field(name=ZERO_WIDTH, value=ZERO_WIDTH)
        page.set_footer(text=f"Page {i} of {total_pages}")
        col_embeds.append(page)
    return col_embeds
