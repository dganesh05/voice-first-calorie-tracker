"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { getSupabaseClient } from "../../lib/supabase";

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export default function SignupPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const handleEmailSignUp = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setMessage("");
    setIsSubmitting(true);

    try {
      const supabase = getSupabaseClient();
      const { error: signUpError } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            full_name: name,
          },
          emailRedirectTo: `${window.location.origin}/logger`,
        },
      });

      if (signUpError) {
        throw signUpError;
      }

      setMessage("Account created. Check your email to confirm your account.");
    } catch (caughtError: unknown) {
      setError(getErrorMessage(caughtError, "Unable to create account."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleSignUp = async () => {
    setError("");
    setIsSubmitting(true);

    try {
      const supabase = getSupabaseClient();
      const { error: oauthError } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: `${window.location.origin}/logger`,
        },
      });

      if (oauthError) {
        throw oauthError;
      }
    } catch (caughtError: unknown) {
      setError(getErrorMessage(caughtError, "Google sign-up failed."));
      setIsSubmitting(false);
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-gradient-to-b from-[#0b1220] via-[#0b1220] to-[#07121a] text-white">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-20 left-1/2 h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-emerald-500/15 blur-[140px]" />
        <div className="absolute top-40 left-0 h-[360px] w-[360px] rounded-full bg-sky-500/10 blur-[120px]" />
        <div className="absolute bottom-10 right-0 h-[420px] w-[420px] rounded-full bg-emerald-500/10 blur-[140px]" />
      </div>

      <div className="relative z-10 flex min-h-screen items-center justify-center px-6 py-10">
        <div className="w-full max-w-md rounded-[32px] bg-white/5 p-8 ring-1 ring-white/10 backdrop-blur">
          <div className="flex flex-col items-center text-center">
            <Image
              src="/vocalorie-icon.PNG"
              alt="Vocalorie"
              width={150}
              height={150}
              className="h-auto w-auto object-contain drop-shadow-[0_0_20px_rgba(16,185,129,0.4)]"
              priority
            />
            <h1 className="mt-5 text-3xl font-semibold tracking-tight">
              Create your account
            </h1>
            <p className="mt-2 text-sm text-white/60">
              Start tracking nutrition with a smooth voice-first experience
            </p>
          </div>

          <div className="mt-8 space-y-3">
            <button
              type="button"
              disabled={isSubmitting}
              onClick={handleGoogleSignUp}
              className="flex w-full items-center justify-center gap-3 rounded-2xl bg-white px-4 py-3 text-sm font-medium text-black transition hover:opacity-90 disabled:opacity-60"
            >
              <span className="text-base">G</span>
              Continue with Google
            </button>

            <button className="flex w-full items-center justify-center gap-3 rounded-2xl bg-black px-4 py-3 text-sm font-medium text-white ring-1 ring-white/15 transition hover:bg-black/80">
              <span className="text-base"></span>
              Continue with Apple
            </button>
          </div>

          <div className="my-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-white/10" />
            <span className="text-xs uppercase tracking-wide text-white/40">or</span>
            <div className="h-px flex-1 bg-white/10" />
          </div>

          <form className="space-y-4" onSubmit={handleEmailSignUp}>
            <div>
              <label className="mb-2 block text-sm text-white/70">Full name</label>
              <input
                type="text"
                placeholder="Enter your full name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                className="w-full rounded-2xl bg-white/10 px-4 py-3 text-sm text-white outline-none ring-1 ring-white/10 placeholder:text-white/35 focus:ring-emerald-500/30"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm text-white/70">Email</label>
              <input
                type="email"
                placeholder="Enter your email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                className="w-full rounded-2xl bg-white/10 px-4 py-3 text-sm text-white outline-none ring-1 ring-white/10 placeholder:text-white/35 focus:ring-emerald-500/30"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm text-white/70">Password</label>
              <input
                type="password"
                placeholder="Create a password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                minLength={8}
                className="w-full rounded-2xl bg-white/10 px-4 py-3 text-sm text-white outline-none ring-1 ring-white/10 placeholder:text-white/35 focus:ring-emerald-500/30"
              />
            </div>

            {error ? <p className="text-sm text-red-300">{error}</p> : null}
            {message ? <p className="text-sm text-emerald-200">{message}</p> : null}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-2xl bg-emerald-500 px-4 py-3 text-sm font-semibold text-[#08131a] transition hover:bg-emerald-400 disabled:opacity-60"
            >
              {isSubmitting ? "Creating account..." : "Create account with Email"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-white/55">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-emerald-300 hover:text-emerald-200">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}