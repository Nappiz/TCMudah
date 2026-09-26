from collections.abc import Sequence
from ipaddress import ip_address
import re
from urllib.parse import urlparse

from app.core import supabase_client
from app.core.config import get_settings
from app.errors.exceptions import BadRequestError

PUBLIC_SETTING_KEYS = frozenset(
    {
        "disable_daftar_kelas",
        "disabled_daftar_kelas_msg",
        "maintenance_mode",
        "maintenance_message",
    }
)
CHECKOUT_SETTING_KEYS = frozenset(
    {
        "checkout_bank_name",
        "checkout_bank_account",
        "checkout_bank_holder",
        "checkout_group_link",
    }
)
ADMIN_SETTING_KEYS = PUBLIC_SETTING_KEYS | CHECKOUT_SETTING_KEYS

DEFAULT_PUBLIC_SETTINGS = {
    "disable_daftar_kelas": "false",
    "disabled_daftar_kelas_msg": "Pendaftaran kelas ditutup sementara.",
    "maintenance_mode": "false",
    "maintenance_message": "Situs sedang dalam maintenance. Silakan coba lagi nanti.",
}

CHECKOUT_ENV_FALLBACKS = {
    "checkout_bank_name": "BANK_NAME",
    "checkout_bank_account": "BANK_ACCOUNT",
    "checkout_bank_holder": "BANK_HOLDER",
    "checkout_group_link": "GROUP_LINK",
}

_BOOLEAN_KEYS = {"disable_daftar_kelas", "maintenance_mode"}
_REQUIRED_TEXT_KEYS = {
    "checkout_bank_name",
    "checkout_bank_account",
    "checkout_bank_holder",
}
_MAX_LENGTHS = {
    "disabled_daftar_kelas_msg": 500,
    "maintenance_message": 500,
    "checkout_bank_name": 120,
    "checkout_bank_account": 80,
    "checkout_bank_holder": 120,
    "checkout_group_link": 500,
}
_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$"
)


def _normalize_keys(keys: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(key.strip() for key in keys if key.strip()))


def read_setting_values(keys: Sequence[str]) -> dict[str, str]:
    normalized = _normalize_keys(keys)
    if not normalized:
        return {}

    response = (
        supabase_client.supabase()
        .table("app_settings")
        .select("key,value")
        .in_("key", normalized)
        .execute()
    )
    return {
        row["key"]: str(row["value"])
        for row in (response.data or [])
        if row.get("key") is not None and row.get("value") is not None
    }


def effective_public_values(keys: Sequence[str]) -> dict[str, str]:
    normalized = _normalize_keys(keys)
    values = read_setting_values(normalized)
    for key in normalized:
        if key not in values and key in DEFAULT_PUBLIC_SETTINGS:
            values[key] = DEFAULT_PUBLIC_SETTINGS[key]
    return {key: values[key] for key in normalized if key in values}


def effective_admin_values(keys: Sequence[str]) -> dict[str, str]:
    normalized = _normalize_keys(keys)
    values = read_setting_values(normalized)
    app_settings = get_settings()

    for key in normalized:
        if key in DEFAULT_PUBLIC_SETTINGS and key not in values:
            values[key] = DEFAULT_PUBLIC_SETTINGS[key]
        if key in CHECKOUT_ENV_FALLBACKS and key not in values:
            env_key = CHECKOUT_ENV_FALLBACKS[key]
            values[key] = str(getattr(app_settings, env_key, "") or "")
    return {key: values[key] for key in normalized if key in values}


def effective_checkout_values() -> dict[str, str]:
    values = effective_admin_values(sorted(CHECKOUT_SETTING_KEYS))
    return {
        key: values.get(key, "").strip()
        for key in CHECKOUT_SETTING_KEYS
    }


def maintenance_state() -> tuple[bool, str]:
    values = effective_public_values(
        ["maintenance_mode", "maintenance_message"]
    )
    message = values.get("maintenance_message", "").strip()
    return values.get("maintenance_mode", "false") == "true", (
        message or DEFAULT_PUBLIC_SETTINGS["maintenance_message"]
    )


def validate_setting_value(key: str, value: str) -> str:
    if key not in ADMIN_SETTING_KEYS:
        raise BadRequestError(detail="Setting tidak tersedia")

    normalized = value.strip()
    if key in _BOOLEAN_KEYS and normalized not in {"true", "false"}:
        raise BadRequestError(detail="Nilai setting boolean harus true atau false")
    if key in _REQUIRED_TEXT_KEYS and not normalized:
        raise BadRequestError(detail="Nilai setting wajib diisi")
    max_length = _MAX_LENGTHS.get(key)
    if max_length is not None and len(normalized) > max_length:
        raise BadRequestError(detail="Nilai setting terlalu panjang")
    if key == "checkout_group_link" and normalized:
        if any(char.isspace() or ord(char) < 32 for char in normalized):
            raise BadRequestError(detail="Link grup WhatsApp tidak valid")
        try:
            parsed = urlparse(normalized)
            hostname = parsed.hostname
            parsed.port
        except (ValueError, UnicodeError):
            raise BadRequestError(detail="Link grup WhatsApp tidak valid")
        if parsed.scheme not in {"http", "https"} or not hostname:
            raise BadRequestError(detail="Link grup WhatsApp tidak valid")
        normalized_hostname = hostname.rstrip(".")
        try:
            ip_address(normalized_hostname)
            valid_hostname = True
        except ValueError:
            valid_hostname = normalized_hostname == "localhost" or bool(
                _HOSTNAME_RE.fullmatch(normalized_hostname)
            )
        if not valid_hostname:
            raise BadRequestError(detail="Link grup WhatsApp tidak valid")
    return normalized
