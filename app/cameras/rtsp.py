"""
RTSP manzilini qismlardan yig'ish va teskarisiga ajratish.

Foydalanuvchi IP, port, login va parolni alohida kiritadi — ular manzil ichiga
foiz-kodlangan (percent-encoded) holda qo'shiladi. Bu shart: parolda `@`, `:`,
`/`, `?` kabi belgilar bo'lsa, ularni to'g'ridan-to'g'ri URL'ga yozish manzilni
buzadi va kamera "ulanib bo'lmadi" deb xato beradi.
"""
from urllib.parse import quote, unquote, urlsplit

DEFAULT_RTSP_PORT = 554

# Ishlab chiqaruvchiga qarab standart oqim yo'llari.
# "main" — asosiy (yuqori sifat), "sub" — kichik oqim (tanish uchun tezroq).
BRAND_PRESETS: dict[str, dict[str, str]] = {
    "hikvision": {
        "label": "Hikvision",
        "main": "/Streaming/Channels/101",
        "sub": "/Streaming/Channels/102",
    },
    "dahua": {
        "label": "Dahua",
        "main": "/cam/realmonitor?channel=1&subtype=0",
        "sub": "/cam/realmonitor?channel=1&subtype=1",
    },
    "reolink": {
        "label": "Reolink",
        "main": "/h264Preview_01_main",
        "sub": "/h264Preview_01_sub",
    },
    "uniview": {
        "label": "Uniview",
        "main": "/media/video1",
        "sub": "/media/video2",
    },
}

CUSTOM_BRAND = "custom"
DEFAULT_BRAND = "hikvision"
DEFAULT_STREAM = "sub"
STREAM_KINDS = ("main", "sub")


def brand_choices() -> list[tuple[str, str]]:
    """UI ro'yxati uchun: [(kalit, ko'rinadigan nom), ...]"""
    choices = [(key, preset["label"]) for key, preset in BRAND_PRESETS.items()]
    choices.append((CUSTOM_BRAND, "Boshqa (yo'lni qo'lda kiritish)"))
    return choices


def stream_path_for(brand: str | None, stream_kind: str | None) -> str | None:
    """Tanlangan ishlab chiqaruvchi va oqim uchun tayyor yo'l; `custom` uchun None."""
    preset = BRAND_PRESETS.get(brand or "")
    if preset is None:
        return None
    return preset.get(stream_kind or DEFAULT_STREAM) or preset[DEFAULT_STREAM]


def normalize_path(path: str | None) -> str:
    path = (path or "").strip()
    if not path:
        return "/"
    return path if path.startswith("/") else "/" + path


def build_rtsp_url(
    host: str | None,
    port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    path: str | None = None,
) -> str | None:
    """Qismlardan to'liq RTSP manzilini yig'adi. Host bo'sh bo'lsa — None."""
    host = (host or "").strip()
    if not host:
        return None

    credentials = ""
    if username:
        credentials = quote(username, safe="")
        if password:
            credentials += ":" + quote(password, safe="")
        credentials += "@"

    return f"rtsp://{credentials}{host}:{int(port or DEFAULT_RTSP_PORT)}{normalize_path(path)}"


def parse_rtsp_url(url: str | None) -> dict | None:
    """
    Tayyor RTSP manzilini qismlarga ajratadi (eski yozuvlarni ko'chirish uchun).
    Ajratib bo'lmasa — None.
    """
    if not url or not url.strip():
        return None
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return None
    if not parts.hostname:
        return None

    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"

    return {
        "host": parts.hostname,
        "port": port or DEFAULT_RTSP_PORT,
        "username": unquote(parts.username) if parts.username else None,
        "password": unquote(parts.password) if parts.password else None,
        "path": path,
    }


def detect_brand(path: str | None) -> tuple[str, str]:
    """Yo'l bo'yicha ishlab chiqaruvchini taxmin qiladi: (brand, stream_kind)."""
    path = normalize_path(path)
    for brand, preset in BRAND_PRESETS.items():
        for kind in STREAM_KINDS:
            if preset[kind] == path:
                return brand, kind
    return CUSTOM_BRAND, DEFAULT_STREAM


def mask_url(url: str | None) -> str:
    """Manzilni parolsiz ko'rsatish: rtsp://admin:•••@192.168.1.64:554/..."""
    if not url:
        return "—"
    parsed = parse_rtsp_url(url)
    if parsed is None:
        return url
    credentials = ""
    if parsed["username"]:
        credentials = parsed["username"]
        if parsed["password"]:
            credentials += ":•••"
        credentials += "@"
    return f"rtsp://{credentials}{parsed['host']}:{parsed['port']}{parsed['path']}"
