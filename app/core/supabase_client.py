from supabase import create_client, Client
from .config import get_settings

_settings = get_settings()
_supabase: Client | None = None

def supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(_settings.SUPABASE_URL, _settings.SUPABASE_SERVICE_ROLE_KEY)
    return _supabase
