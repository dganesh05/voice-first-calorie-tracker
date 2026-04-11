## Plan: Free Security Baseline for Vocalorie

Implement a layered, zero-cost security foundation using Supabase Auth + RLS, backend token verification, strict input controls, and operational hardening. This approach secures user data end-to-end without paid services and aligns with strict privacy defaults.

**Steps**
1. Phase 1: Secrets and configuration lockdown
2. Rotate all leaked or previously committed keys (USDA, Groq, Tavily, Supabase) and remove hardcoded credential examples that encourage service-role usage in client-facing contexts.
3. Split backend-only vs client-safe environment variables, ensuring service-role key is never available to the browser and only used in trusted backend paths that require elevated privileges.
4. Add environment validation at startup (fail fast when required vars are missing or malformed), and add .env.example with placeholders only. *parallel with step 5*
5. Update README security section with least-privilege guidance and key-rotation workflow. *parallel with step 4*
6. Phase 2: Authentication and session enforcement
7. Implement Supabase Auth in Next.js login/signup flows (email+password and Google OAuth), replacing UI-only forms with real sign-in/sign-up handlers and session-aware redirects.
8. Add route protection in Next.js for journal/logger/profile so anonymous users are redirected to login.
9. Propagate Supabase JWT from frontend to FastAPI for protected endpoints and verify token signature/claims server-side on each authenticated request.
10. Add identity binding: backend operations must execute in user context and never trust client-submitted user_id fields. *depends on 9*
11. Phase 3: Data-layer authorization (strict privacy)
12. Design user-owned tables (profiles, journal_entries, meal_logs) with owner column tied to auth.uid().
13. Enable Row Level Security for all user-data tables and add deny-by-default policies; allow read/write only where row owner equals auth.uid().
14. Add explicit policies for insert/update/delete separation and prevent cross-user reads through joins/views.
15. Add migration scripts and policy verification checks (positive and negative cases). *depends on 12-14*
16. Phase 4: API and input hardening
17. Restrict CORS to explicit origins by environment, remove wildcard method/header posture where unnecessary, and disable credentials unless required.
18. Add request validation for all endpoint inputs (query length, allowed characters, file size/type limits for audio uploads).
19. Add rate limiting (IP + user-based quotas) to abuse-prone endpoints: /api/voice and /api/foods/search.
20. Add safe error handling: remove raw provider error prints from responses/logs, redact sensitive fields, and return normalized error payloads.
21. Phase 5: Security headers and transport
22. Add HTTP security headers in Next.js and backend responses (CSP, frame-ancestors, nosniff, referrer-policy, strict transport assumptions for production).
23. Ensure secure cookie settings for auth sessions (httpOnly, secure in production, sameSite) and avoid storing sensitive tokens in localStorage.
24. Enforce HTTPS-only deployment guidance and trusted reverse-proxy configuration.
25. Phase 6: Verification and operational readiness
26. Add automated security checks in CI: dependency audit, static linting, and secret scanning before merge.
27. Create a minimal abuse test matrix (unauthenticated access, cross-user data access, oversized upload, repeated voice calls).
28. Add incident playbook notes (key compromise, forced logout, token revocation, suspicious traffic response).

**Relevant files**
- /home/divya_ganesh/projects/Software engineering/NEW FOLDER/voice-first-calorie-tracker/main.py — add auth dependency, token verification, input validation, rate limits, safer error handling, CORS tightening.
- /home/divya_ganesh/projects/Software engineering/NEW FOLDER/voice-first-calorie-tracker/supabase_client.py — separate admin client usage and add safer initialization/validation.
- /home/divya_ganesh/projects/Software engineering/NEW FOLDER/voice-first-calorie-tracker/app/login/page.tsx — wire real sign-in actions and OAuth start.
- /home/divya_ganesh/projects/Software engineering/NEW FOLDER/voice-first-calorie-tracker/app/signup/page.tsx — wire real sign-up actions and post-signup verification UX.
- /home/divya_ganesh/projects/Software engineering/NEW FOLDER/voice-first-calorie-tracker/app/logger/page.tsx — include authenticated API calls with bearer token and auth-aware states.
- /home/divya_ganesh/projects/Software engineering/NEW FOLDER/voice-first-calorie-tracker/app/journal/page.tsx — protect page and load only authenticated user data.
- /home/divya_ganesh/projects/Software engineering/NEW FOLDER/voice-first-calorie-tracker/app/profile/page.tsx — protect page and bind updates to current user identity.
- /home/divya_ganesh/projects/Software engineering/NEW FOLDER/voice-first-calorie-tracker/README.md — add security setup and rotation guidance.
- /home/divya_ganesh/projects/Software engineering/NEW FOLDER/voice-first-calorie-tracker/requirements.txt — add auth/jwt/rate-limit/validation dependencies.
- /home/divya_ganesh/projects/Software engineering/NEW FOLDER/voice-first-calorie-tracker/.env.example — add non-secret template and variable documentation.

**Verification**
1. Auth flow checks: sign up, email login, Google login, logout, session refresh, and protected route redirect behavior.
2. Backend auth checks: protected endpoints reject missing/invalid/expired JWT and accept valid JWT.
3. RLS checks: user A cannot read/update/delete user B rows; service-role path is inaccessible from frontend.
4. Upload abuse checks: oversized file, wrong mime type, malformed multipart body, and rapid repeated requests are blocked.
5. CORS checks: allowed origins pass; untrusted origins fail preflight and credentialed requests.
6. Secret hygiene checks: no real keys in repo history going forward; secret scanner and dependency audit pass in CI.

**Decisions**
- Include: Supabase Auth (email + Google), strict RLS, backend JWT verification, rate limiting, and input validation.
- Exclude for now: paid WAF/CDN bot products, enterprise SIEM, dedicated HSM/KMS services.
- Use strict privacy defaults from day one because meal/journal data is user-personal.

**Further Considerations**
1. Rate limiting backend choice: in-memory for local MVP vs Redis-backed for multi-instance deployment. Recommendation: start in-memory now, upgrade before horizontal scaling.
2. Voice file retention: immediate delete after transcription vs short retention for debugging. Recommendation: immediate delete by default, opt-in debug retention with admin-only toggle.
3. Account recovery UX: magic link backup vs password reset only. Recommendation: support password reset and add magic link later if support burden increases.
