import re
import unicodedata


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\t", " ")
    normalized = re.sub(r"[ ]+", " ", normalized)
    normalized = "\n".join(line.strip() for line in normalized.splitlines())
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()
