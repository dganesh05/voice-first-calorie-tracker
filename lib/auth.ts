import { getAccessToken, getSessionUser } from "./supabase";

export async function ensureAuthenticatedOrRedirect(
  redirectTo = "/login"
): Promise<boolean> {
  const user = await getSessionUser();

  if (!user) {
    if (typeof window !== "undefined") {
      window.location.href = redirectTo;
    }
    return false;
  }

  return true;
}

export async function requireAccessTokenOrRedirect(
  redirectTo = "/login"
): Promise<string | null> {
  const accessToken = await getAccessToken();

  if (!accessToken) {
    if (typeof window !== "undefined") {
      window.location.href = redirectTo;
    }
    return null;
  }

  return accessToken;
}
