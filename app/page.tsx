import Image from "next/image";
import Link from "next/link";

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-x-hidden bg-gradient-to-b from-[#0b1220] via-[#0b1220] to-[#07121a] text-white">

      {/* Background glow */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-32 left-1/2 h-[600px] w-[600px] -translate-x-1/2 rounded-full bg-emerald-500/20 blur-[140px]" />
        <div className="absolute top-40 left-10 h-[400px] w-[400px] rounded-full bg-sky-500/10 blur-[120px]" />
        <div className="absolute bottom-0 right-0 h-[450px] w-[450px] rounded-full bg-emerald-500/10 blur-[140px]" />
      </div>

      {/* Navbar */}
      <header className="relative z-20 mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Link href="/" className="flex items-center gap-3">
          <Image
            src="/vocalorie-icon.PNG"
            alt="Vocalorie"
            width={150}
            height={150}
            className="object-contain drop-shadow-[0_0_14px_rgba(16,185,129,0.45)]"
            priority
          />
          <div className="leading-tight">
            <p className="text-sm text-white/70">Voice-first calorie tracking</p>
            <p className="text-lg font-semibold tracking-tight text-white">
              Vocalorie
            </p>
          </div>
        </Link>

        <nav className="hidden items-center gap-6 text-sm text-white/70 md:flex">
          <a href="#how" className="hover:text-white">How it works</a>
          <a href="#features" className="hover:text-white">Features</a>
          <Link href="/logger">Logger</Link>
          <Link href="/journal">Journal</Link>
          <Link href="/profile">Profile</Link>
        </nav>

        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="rounded-full bg-white/10 px-4 py-2 text-sm text-white ring-1 ring-white/15 hover:bg-white/15"
          >
            Sign in
          </Link>
          <Link
            href="/signup"
            className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-[#08131a] hover:bg-emerald-400"
          >
            Get started
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 pt-12 pb-20">
        <div className="grid gap-16 md:grid-cols-2 md:items-center">

          {/* LEFT */}
          <div>

            {/* badge */}
            <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs text-white/80 ring-1 ring-white/15">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              Log meals in under 10 seconds
            </div>

            {/* text logo */}
            <div className="mt-6">
              <h2 className="text-3xl md:text-4xl font-semibold tracking-tight">
                <span className="text-white/80">Vocal</span>
                <span className="text-emerald-400 drop-shadow-[0_0_12px_rgba(16,185,129,0.6)]">
                  orie
                </span>
              </h2>
            </div>

            {/* headline */}
            <h1 className="mt-6 text-4xl md:text-6xl font-semibold leading-tight">
              Track calories by{" "}
              <span className="text-emerald-300">speaking</span>.
              <br />
              No typing. No searching.
            </h1>

            {/* description */}
            <p className="mt-5 max-w-xl text-lg text-white/70">
              Vocalorie turns your voice into a clean meal log. Speak what you ate,
              confirm the result, and instantly track calories and nutrition with a
              smooth, modern experience.
            </p>

            {/* buttons */}
            <div className="mt-8 flex gap-4">
              <Link
                href="/logger"
                className="rounded-full bg-emerald-500 px-6 py-3 text-sm font-semibold text-[#08131a] hover:bg-emerald-400"
              >
                Start logging
              </Link>
              <a
                href="#how"
                className="rounded-full bg-white/10 px-6 py-3 text-sm font-semibold text-white ring-1 ring-white/15 hover:bg-white/15"
              >
                See how it works
              </a>
            </div>

            {/* stats */}
            <div className="mt-10 grid grid-cols-3 gap-4 text-center">
              <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
                <p className="text-2xl font-semibold">10s</p>
                <p className="text-xs text-white/60">Average log time</p>
              </div>
              <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
                <p className="text-2xl font-semibold">1 tap</p>
                <p className="text-xs text-white/60">To start speaking</p>
              </div>
              <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
                <p className="text-2xl font-semibold">AI</p>
                <p className="text-xs text-white/60">Auto recognition</p>
              </div>
            </div>
          </div>

          {/* RIGHT (floating image) */}
          <div className="relative flex justify-center">

            <div className="absolute h-[600px] w-[600px] rounded-full bg-emerald-500/20 blur-[140px]" />
            <div className="absolute h-[500px] w-[500px] rounded-full bg-sky-500/10 blur-[120px]" />

            <Image
              src="/vocalorie-glass-hero-new.png"
              alt="Vocalorie"
              width={540}
              height={540}
              className="relative z-10 max-w-[520px] object-contain opacity-95 mix-blend-screen drop-shadow-[0_0_80px_rgba(16,185,129,0.35)] animate-[float_6s_ease-in-out_infinite]"
              priority
            />
          </div>

        </div>
      </section>

      {/* HOW */}
      <section id="how" className="relative z-10 mx-auto max-w-6xl px-6 pb-12">
        <h2 className="text-xl font-semibold">How it works</h2>

        <div className="mt-6 grid md:grid-cols-3 gap-4">
          <StepCard title="1. Speak" desc="Describe your meal naturally." />
          <StepCard title="2. Understand" desc="AI extracts food + calories." />
          <StepCard title="3. Log" desc="Confirm and save instantly." />
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="relative z-10 mx-auto max-w-6xl px-6 pb-20">
        <h2 className="text-xl font-semibold">Features</h2>

        <div className="mt-6 grid md:grid-cols-3 gap-4">
          <FeatureCard title="Smooth UI" desc="Clear and responsive states." />
          <FeatureCard title="Fast logging" desc="No typing, just speak." />
          <FeatureCard title="Smart tracking" desc="Daily insights + history." />
        </div>
      </section>

    </main>
  );
}

function StepCard({ title, desc }: any) {
  return (
    <div className="rounded-3xl bg-white/5 p-5 ring-1 ring-white/10 hover:bg-white/10">
      <p className="font-semibold">{title}</p>
      <p className="text-sm text-white/70 mt-2">{desc}</p>
    </div>
  );
}

function FeatureCard({ title, desc }: any) {
  return (
    <div className="rounded-3xl bg-white/5 p-5 ring-1 ring-white/10 hover:bg-white/10">
      <p className="font-semibold text-emerald-300">{title}</p>
      <p className="text-sm text-white/70 mt-2">{desc}</p>
    </div>
  );
}