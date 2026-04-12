import { NextRequest, NextResponse } from "next/server";
import { getTokenFromRequest, verifyAuth } from "./lib/auth-server";

const PROTECTED_ROUTES = ["/logger", "/journal", "/profile"];
const AUTH_ROUTES = ["/login", "/signup"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Check if accessing protected route
  const isProtected = PROTECTED_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`)
  );

  // Check if accessing auth page
  const isAuthPage = AUTH_ROUTES.some((route) => pathname === route);

  const token = getTokenFromRequest(request);
  const authToken = token ? await verifyAuth(token) : null;
  const isAuthenticated = !!authToken;

  // Client auth currently stores session outside server-readable cookies.
  // Avoid redirect loops by redirecting only when a presented token is invalid.
  if (isProtected && token && !isAuthenticated) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Auth pages: redirect authenticated users to logger
  if (isAuthPage && isAuthenticated) {
    return NextResponse.redirect(new URL("/logger", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/logger/:path*", "/journal/:path*", "/profile/:path*", "/login", "/signup"],
};
