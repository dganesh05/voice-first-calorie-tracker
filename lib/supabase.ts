import { createClient } from "@supabase/supabase-js";

type SessionUser = {
  id: string;
  email: string | null;
  fullName: string | null;
};

let supabaseClient: ReturnType<typeof createClient> | null = null;
let cachedSessionUser: SessionUser | null = null;
let cachedAccessToken: string | null = null;
let cacheExpiresAt = 0;
let inFlightSessionRequest: Promise<SessionUser | null> | null = null;

const SESSION_CACHE_MS = 15_000;

export function getSupabaseClient() {
  if (supabaseClient) {
    return supabaseClient;
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error(
      "Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY in environment."
    );
  }

  supabaseClient = createClient(supabaseUrl, supabaseAnonKey);
  return supabaseClient;
}

function isCacheFresh() {
  return Date.now() < cacheExpiresAt;
}

function cacheSessionData(user: SessionUser | null, token: string | null) {
  cachedSessionUser = user;
  cachedAccessToken = token;
  cacheExpiresAt = Date.now() + SESSION_CACHE_MS;
}

export function clearCachedSession() {
  cachedSessionUser = null;
  cachedAccessToken = null;
  cacheExpiresAt = 0;
}

export async function getSessionUser(forceRefresh = false): Promise<SessionUser | null> {
  if (!forceRefresh && isCacheFresh()) {
    return cachedSessionUser;
  }

  if (inFlightSessionRequest) {
    return inFlightSessionRequest;
  }

  const supabase = getSupabaseClient();
  inFlightSessionRequest = (async () => {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    const sessionUser = session?.user;
    const user: SessionUser | null = sessionUser
      ? {
          id: sessionUser.id,
          email: sessionUser.email ?? null,
          fullName:
            (typeof sessionUser.user_metadata?.full_name === "string"
              ? sessionUser.user_metadata.full_name
              : null) ??
            (typeof sessionUser.user_metadata?.name === "string"
              ? sessionUser.user_metadata.name
              : null),
        }
      : null;

    cacheSessionData(user, session?.access_token ?? null);
    return user;
  })();

  try {
    return await inFlightSessionRequest;
  } finally {
    inFlightSessionRequest = null;
  }
}

export async function getAccessToken(): Promise<string | null> {
  if (isCacheFresh()) {
    return cachedAccessToken;
  }

  await getSessionUser(true);
  return cachedAccessToken;
}
