import Image from "next/image";
import Link from "next/link";

export default function LoginPage() {
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
              src="/vocalorie-icon.png"
              alt="Vocalorie"
              width={250}
              height={250}
              className="object-contain drop-shadow-[0_0_20px_rgba(16,185,129,0.4)]"
              priority
            />
            <h1 className="mt-5 text-3xl font-semibold tracking-tight">
              Welcome back
            </h1>
            <p className="mt-2 text-sm text-white/60">
              Sign in to continue your voice-first nutrition journey
            </p>
          </div>

          <div className="mt-8 space-y-3">
            <button className="flex w-full items-center justify-center gap-3 rounded-2xl bg-white px-4 py-3 text-sm font-medium text-black transition hover:opacity-90">
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

          <form className="space-y-4">
            <div>
              <label className="mb-2 block text-sm text-white/70">Email</label>
              <input
                type="email"
                placeholder="Enter your email"
                className="w-full rounded-2xl bg-white/10 px-4 py-3 text-sm text-white outline-none ring-1 ring-white/10 placeholder:text-white/35 focus:ring-emerald-500/30"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm text-white/70">Password</label>
              <input
                type="password"
                placeholder="Enter your password"
                className="w-full rounded-2xl bg-white/10 px-4 py-3 text-sm text-white outline-none ring-1 ring-white/10 placeholder:text-white/35 focus:ring-emerald-500/30"
              />
            </div>

            <button className="w-full rounded-2xl bg-emerald-500 px-4 py-3 text-sm font-semibold text-[#08131a] transition hover:bg-emerald-400">
              Sign in with Email
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-white/55">
            Don’t have an account?{" "}
            <Link href="/signup" className="font-medium text-emerald-300 hover:text-emerald-200">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}