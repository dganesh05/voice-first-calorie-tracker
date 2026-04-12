"use client";

import Link from "next/link";
import AuthNavActions from "./AuthNavActions";
import Logo from "./Logo";

export default function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-gray-100 bg-white/85 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Logo small />

        <nav className="hidden items-center gap-6 text-sm text-gray-700 md:flex">
          <Link href="/" className="hover:text-green-700">
            Home
          </Link>
          <Link href="/logger" className="hover:text-green-700">
            Logger
          </Link>
          <Link href="/journal" className="hover:text-green-700">
            Journal
          </Link>
          <Link href="/profile" className="hover:text-green-700">
            Profile
          </Link>
        </nav>

        <div className="flex items-center gap-3">
          <AuthNavActions
            signInClassName="text-sm text-gray-700 hover:text-green-700"
            signOutClassName="text-sm text-gray-700 hover:text-green-700"
            signUpClassName="rounded-full bg-green-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-green-700"
          />
        </div>
      </div>
    </header>
  );
}