from app.core.rpc import unwrap_rpc_object
from app.core.supabase_client import supabase


def get_public_catalog():
    response = supabase().rpc("get_public_catalog", {}).execute()
    return unwrap_rpc_object(response.data, rpc_name="get_public_catalog")

