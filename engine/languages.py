"""Language codes the copy steps write in (project.yaml `languages`), and how a prompt names them.

Copy is written for each market by the text backend, never translated word for word from English. A code the table
doesn't know is still used; the prompt names it by its code."""
from __future__ import annotations

NAMES = {
    "en": "English", "en-US": "American English", "en-GB": "British English", "es": "Spanish", "es-MX": "Mexican Spanish",
    "fr": "French", "de": "German", "it": "Italian", "pt": "Portuguese", "pt-BR": "Brazilian Portuguese", "nl": "Dutch",
    "sv": "Swedish", "da": "Danish", "nb": "Norwegian", "no": "Norwegian", "fi": "Finnish", "pl": "Polish",
    "cs": "Czech", "sk": "Slovak", "hu": "Hungarian", "ro": "Romanian", "bg": "Bulgarian", "el": "Greek",
    "tr": "Turkish", "ru": "Russian", "uk": "Ukrainian", "ar": "Arabic", "he": "Hebrew", "fa": "Persian",
    "hi": "Hindi", "bn": "Bengali", "ur": "Urdu", "ta": "Tamil", "id": "Indonesian", "ms": "Malay", "th": "Thai",
    "vi": "Vietnamese", "tl": "Filipino", "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "zh-CN": "Simplified Chinese",
    "zh-TW": "Traditional Chinese", "sw": "Swahili",
}
RTL = {"ar", "he", "fa", "ur"}


def name(code: str) -> str:
    return NAMES.get(code) or NAMES.get(code.split("-")[0]) or code


def is_rtl(code: str) -> bool:
    return code.split("-")[0] in RTL


def instruction(code: str) -> str:
    """The line every copy prompt carries for its language."""
    if code.split("-")[0] == "en" and code in ("en", "en-US", "en-GB"):
        return f"Write in {name(code)}."
    return (f"Write natively in {name(code)} for shoppers in that market, the way a local copywriter would: idioms, "
            f"units and register of that market. Do not translate from English.")


def suffix(code: str, codes: list[str]) -> str:
    """The file name part for a language: none for a project's only language, `.<code>` otherwise."""
    return "" if len(codes) == 1 else f".{code}"
