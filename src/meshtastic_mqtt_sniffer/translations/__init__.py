import locale
import os

from meshtastic_mqtt_sniffer.translations.en import EN
from meshtastic_mqtt_sniffer.translations.tr import TR

TEXT = {
    "en": EN,
    "tr": TR,
}


def resolve_language(language: str) -> str:
    """Resolve an output language, detecting the system locale when requested.

    Args:
        language (str): Requested language code: ``auto``, ``en``, or ``tr``.

    Returns:
        str: The resolved English or Turkish language code.
    """
    if language != "auto":
        return language
    detected = locale.getlocale()[0] or os.environ.get("LANG", "")
    return "tr" if detected.lower().startswith("tr") else "en"


def tr(language: str, key: str, **values: object) -> str:
    """Format a localized message.

    Args:
        language (str): Resolved language code used to select translations.
        key (str): Translation key in the message catalog.
        **values (object): Named values interpolated into the translated message.

    Returns:
        str: The formatted localized message.
    """
    return TEXT[language][key].format(**values)
