"""Devanagari checks for bilingual sources (S1 report: Hindi and bilingual; data-pipeline.md §7).

Gazette and circular PDFs often carry Hindi in a legacy font encoding or with a broken ToUnicode map: the text
layer then holds Devanagari code points in impossible orders ("िारा" for धारा, "अिधसूिचत" for अधिसूचित).
A dependent vowel sign or virama must follow a consonant; the share of signs that don't is the signal.
Citations use the English text: Hindi lines are recognised here and never indexed.
"""

from __future__ import annotations

_CONSONANTS = frozenset(range(0x0915, 0x093A)) | frozenset(range(0x0958, 0x0960)) | {0x093C}
_SIGNS = frozenset(range(0x093E, 0x094E)) | {0x0962, 0x0963}

# A mixed page needs this many Devanagari letters before its Hindi is judged (Gazette mastheads have ~30).
MIN_LETTERS_TO_JUDGE = 100
# Share of misplaced signs above which a text layer is undecodable (S1 corpus: 10-26%; clean Unicode: ~0%).
INVALID_SIGN_SHARE = 0.05
# A page whose letters are mostly Devanagari belongs to the Hindi half of a bilingual Gazette.
HINDI_PAGE_SHARE = 0.6


def is_devanagari(ch: str) -> bool:
    return 0x0900 <= ord(ch) <= 0x097F


def devanagari_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(map(is_devanagari, letters)) / len(letters) if letters else 0.0


def is_hindi_line(text: str) -> bool:
    return devanagari_share(text) > 0.5


def invalid_sign_share(text: str) -> float:
    signs = invalid = 0
    prev = " "
    for ch in text:
        if ord(ch) in _SIGNS:
            signs += 1
            invalid += ord(prev) not in _CONSONANTS
        prev = ch
    return invalid / signs if signs else 0.0


def is_hindi_page(text: str) -> bool:
    return devanagari_share(text) >= HINDI_PAGE_SHARE


def has_undecodable_hindi(text: str) -> bool:
    """A page with enough Hindi to matter whose text layer cannot be trusted: OCR it instead (S1 follow-up)."""
    letters = sum(map(is_devanagari, text))
    return letters >= MIN_LETTERS_TO_JUDGE and invalid_sign_share(text) >= INVALID_SIGN_SHARE
