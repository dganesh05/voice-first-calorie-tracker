"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import AuthNavActions from "../components/AuthNavActions";

const steps = [
  {
    title: "Speak naturally",
    desc: "Say what you ate in plain language.",
  },
  {
    title: "AI understands",
    desc: "Extracts foods and nutrition instantly.",
  },
  {
    title: "Track instantly",
    desc: "Logged into your dashboard automatically.",
  },
];

const features = [
  {
    title: "Voice-first logging",
    desc: "No typing required.",
  },
  {
    title: "Fast tracking",
    desc: "Log meals in seconds.",
  },
  {
    title: "Clean UI",
    desc: "Modern and distraction-free.",
  },
];

const stats = [
  { value: "10s", label: "Average log time" },
  { value: "1 tap", label: "To start speaking" },
  { value: "AI", label: "Auto recognition" },
];

export default function Home() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <main className="relative min-h-screen overflow-x-hidden bg-gradient-to-b from-[#0b1220] via-[#0b1220] to-[#07121a] text-white pb-10">

      {/* BACKGROUND GLOW */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-[-120px] h-[360px] w-[360px] -translate-x-1/2 rounded-full bg-emerald-500/20 blur-[120px]" />
        <div className="absolute bottom-[-60px] right-[-60px] h-[260px] w-[260px] rounded-full bg-emerald-500/10 blur-[100px]" />
      </div>

      {/* HEADER */}
      <header className="relative z-30 mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">

        {/* LOGO */}
        <Link href="/" className="flex items-center gap-3">
          <Image
            src="/vocalorie-icon.PNG"
            alt="logo"
            width={50}
            height={50}
            style={{ height: "auto" }}
            className="h-10 w-auto"
          />
          <div>
            <p className="text-xs text-white/60">Voice-first calorie tracking</p>
            <p className="font-semibold">Vocalorie</p>
          </div>
        </Link>

        {/* DESKTOP NAV */}
        <nav className="hidden md:flex gap-6 text-sm text-white/70">
          <Link href="/logger">Logger</Link>
          <Link href="/journal">Journal</Link>
          <Link href="/profile">Profile</Link>
        </nav>

        <div className="flex items-center gap-3">
          <div className="hidden md:flex">
            <AuthNavActions
              signInClassName="rounded-full bg-white/10 px-4 py-2 text-sm text-white ring-1 ring-white/15 hover:bg-white/15"
              signOutClassName="rounded-full bg-white/10 px-4 py-2 text-sm text-white ring-1 ring-white/15 hover:bg-white/15"
            />
          </div>

          {/* MOBILE MENU BUTTON */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden h-10 w-10 flex items-center justify-center rounded-full bg-white/10"
          >
            ☰
          </button>
        </div>
      </header>

      {/* MOBILE DROPDOWN */}
      {menuOpen && (
        <div className="mx-4 mt-2 md:hidden">
          <div className="rounded-2xl bg-white/10 backdrop-blur-lg p-3 space-y-2">
            <Link href="/" className="block p-3 rounded-xl hover:bg-white/10">Home</Link>
            <Link href="/logger" className="block p-3 rounded-xl hover:bg-white/10">Logger</Link>
            <Link href="/journal" className="block p-3 rounded-xl hover:bg-white/10">Journal</Link>
            <Link href="/profile" className="block p-3 rounded-xl hover:bg-white/10">Profile</Link>
            <div className="pt-2">
              <AuthNavActions
                signInClassName="block rounded-xl bg-white/10 px-4 py-3 text-center text-sm text-white ring-1 ring-white/15 hover:bg-white/15"
                signOutClassName="block w-full rounded-xl bg-white/10 px-4 py-3 text-center text-sm text-white ring-1 ring-white/15 hover:bg-white/15"
              />
            </div>
          </div>
        </div>
      )}

      {/* HERO */}
      <section className="relative z-10 mx-auto max-w-6xl px-4 sm:px-6 pt-8 pb-16">

        <div className="grid gap-10 lg:grid-cols-2 items-center">

          {/* TEXT */}
          <div>
            <div className="text-sm text-emerald-400 mb-3">
              ● Log meals in under 10 seconds
            </div>

            <h1 className="text-[2.5rem] sm:text-5xl lg:text-6xl font-semibold leading-tight">
              Track calories by{" "}
              <span className="text-emerald-400">speaking</span>.
              <br />
              No typing. No searching.
            </h1>

            <p className="mt-4 text-white/70 max-w-xl">
              Vocalorie turns your voice into a clean meal log.
            </p>

            {/* BUTTONS */}
            <div className="mt-6 flex flex-col sm:flex-row gap-3">
              <Link href="/logger" className="bg-emerald-500 text-black px-6 py-3 rounded-full text-center">
                Start logging
              </Link>
              <a href="#how" className="bg-white/10 px-6 py-3 rounded-full text-center">
                See how it works
              </a>
            </div>

            {/* STATS */}
            <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {stats.map((s) => (
                <div key={s.label} className="bg-white/5 p-4 rounded-xl text-center">
                  <p className="text-xl font-semibold">{s.value}</p>
                  <p className="text-xs text-white/60">{s.label}</p>
                </div>
              ))}
            </div>
          </div>

          {/* IMAGE */}
          <div className="flex justify-center">
            <Image
              src="/vocalorie-glass-hero-new.png"
              alt="hero"
              width={400}
              height={400}
              style={{ height: "auto" }}
              className="animate-[float_6s_ease-in-out_infinite] w-full max-w-[300px] sm:max-w-[400px]"
            />
          </div>
        </div>
      </section>

      {/* HOW */}
      <section id="how" className="px-4 sm:px-6 max-w-6xl mx-auto mb-16">
        <h2 className="text-2xl mb-4">How it works</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {steps.map((s, i) => (
            <div key={i} className="bg-white/5 p-5 rounded-xl">
              <p className="font-semibold">{s.title}</p>
              <p className="text-sm text-white/70 mt-2">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* FEATURES */}
      <section className="px-4 sm:px-6 max-w-6xl mx-auto mb-20">
        <h2 className="text-2xl mb-4">Features</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {features.map((f, i) => (
            <div key={i} className="bg-white/5 p-5 rounded-xl">
              <p className="text-emerald-400 font-semibold">{f.title}</p>
              <p className="text-sm text-white/70 mt-2">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

    </main>
  );
}