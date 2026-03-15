import re
import unicodedata
from urllib.parse import urlparse


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "n-a"


def looks_like_url(value: str) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)
