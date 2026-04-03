from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv(override=True)

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()
SUPABASE_SERVICE_ROLE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
SUPABASE_ANON_KEY = (os.getenv("SUPABASE_ANON_KEY") or "").strip()

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing. Set it in .env.")

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is missing. Set it in .env.")

# Admin client: privileged DB writes that should bypass RLS.
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Auth client: sign-up/sign-in/get_user flows using normal client privileges.
# If SUPABASE_ANON_KEY is not provided, fall back to service role to avoid startup failure.
auth_supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY or SUPABASE_SERVICE_ROLE_KEY)