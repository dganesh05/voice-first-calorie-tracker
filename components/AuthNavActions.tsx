"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { clearCachedSession, getSessionUser, getSupabaseClient } from "../lib/supabase";

type AuthNavActionsProps = {
  signInClassName: string;
  signOutClassName?: string;
  signUpClassName?: string;
  signedOutLabel?: string;
  signedInLabel?: string;
  signingOutLabel?: string;
  signUpLabel?: string;
};

export default function AuthNavActions({
  signInClassName,
  signOutClassName,
  signUpClassName,
  signedOutLabel = "Sign in",
  signedInLabel = "Sign out",
  signingOutLabel = "Signing out...",
  signUpLabel = "Sign Up",
}: AuthNavActionsProps) {
  const [isSignedIn, setIsSignedIn] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const supabase = getSupabaseClient();

    const syncSessionState = async () => {
      try {
        const user = await getSessionUser(true);
        if (isMounted) {
          setIsSignedIn(Boolean(user));
        }
      } catch {
        if (isMounted) {
          setIsSignedIn(false);
        }
      }
    };

    syncSessionState();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      clearCachedSession();
      setIsSignedIn(Boolean(session?.user));
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const handleSignOut = async () => {
    setIsSigningOut(true);

    try {
      const supabase = getSupabaseClient();
      await supabase.auth.signOut();
      clearCachedSession();
      window.location.href = "/login";
    } finally {
      setIsSigningOut(false);
    }
  };

  if (isSignedIn) {
    return (
      <button
        type="button"
        onClick={handleSignOut}
        disabled={isSigningOut}
        className={signOutClassName ?? signInClassName}
      >
        {isSigningOut ? signingOutLabel : signedInLabel}
      </button>
    );
  }

  return (
    <>
      <Link href="/login" className={signInClassName}>
        {signedOutLabel}
      </Link>
      {signUpClassName ? (
        <Link href="/signup" className={signUpClassName}>
          {signUpLabel}
        </Link>
      ) : null}
    </>
  );
}