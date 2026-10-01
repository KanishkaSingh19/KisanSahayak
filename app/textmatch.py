"""Finding a word or name inside a farmer's message, in English, Hinglish, Hindi or Punjabi.

One rule for the whole app (question routing, crop and place names, market prices):
- Latin script: whole words only ("rate" does not match "pirate").
- Devanagari / Gurmukhi names (crops, places), `whole_word=True`: the name must not be part of a
  longer word. Vowel signs and nasal marks after it are allowed ("धानों" still contains धान), another
  letter is not ("तिलहन", oilseeds, does not contain तिल, sesame).
- Devanagari / Gurmukhi topic words, `whole_word=False`: stems that Hindi and Punjabi extend into
  longer words, so they match inside them ("खरपतवारनाशक", herbicide, contains खरपतवार, weed;
  "ਸੋਧਣ" contains the stem ਸੋਧ).
"""

import re
import unicodedata


def _indic_letter(ch: str) -> bool:
    """A Devanagari or Gurmukhi letter (not a vowel sign, nasal mark or punctuation)."""
    return ("ऀ" <= ch <= "੿") and unicodedata.category(ch) == "Lo"


def contains_term(term: str, text: str, whole_word: bool = True) -> bool:
    """True if `term` appears in `text` (case-insensitive, any script); see the module notes for
    when Indian-script terms must be whole words (names) and when they may be stems (topic words)."""
    term = unicodedata.normalize("NFC", term.lower().strip())
    text = unicodedata.normalize("NFC", text.lower())
    if not term:
        return False
    if term.isascii():
        return bool(re.search(rf"\b{re.escape(term)}\b", text))
    if not whole_word:
        return term in text
    start = text.find(term)
    while start != -1:
        end = start + len(term)
        before_ok = start == 0 or not _indic_letter(text[start - 1])
        after_ok = end == len(text) or not _indic_letter(text[end])
        if before_ok and after_ok:
            return True
        start = text.find(term, start + 1)
    return False
