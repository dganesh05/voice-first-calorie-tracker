from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv(override=True)

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()
SUPABASE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing. Set it in .env.")

if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is missing. Set it in .env.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)