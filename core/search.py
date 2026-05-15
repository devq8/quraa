import re


_TASHKEEL_RE = re.compile(r"[ً-ْٰـ]")
_WHITESPACE_RE = re.compile(r"\s+")
_ALEF_VARIANTS = str.maketrans({
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ٱ": "ا",
    "ى": "ي",
    "ؤ": "و",
    "ئ": "ي",
})


def normalize_arabic(text):
    if not text:
        return ""
    text = text.lower()
    text = _TASHKEEL_RE.sub("", text)
    text = text.translate(_ALEF_VARIANTS)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def biography_search_text(*fields):
    parts = [f for f in fields if f]
    return normalize_arabic(" ".join(parts))
