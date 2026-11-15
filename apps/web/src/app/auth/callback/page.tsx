"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorState, Loading } from "@/components/states/states";
import { api } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth-context";

// Supabase lands here after Google / magic link (the client exchanges the code itself).
// Then: no connections -> /onboarding, otherwise -> /today (S30 flow diagram).
export default function AuthCallbackPage() {
  const { status } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (status !== "signed_in") return;
    let active = true;
    api()
      .me()
      .then((me) => {
        if (active) router.replace(me.connections.length === 0 ? "/onboarding" : "/today");
      })
      .catch((e) => active && setError(e));
    return () => {
      active = false;
    };
  }, [status, router, attempt]);

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-4 px-4 py-24">
      {status === "signed_out" ? (
        <>
          <p>That sign-in link didn&apos;t work or has expired.</p>
          <Link className="underline" href="/">
            Back to sign in
          </Link>
        </>
      ) : error ? (
        <ErrorState
          error={error}
          onRetry={() => {
            setError(null);
            setAttempt((n) => n + 1);
          }}
        />
      ) : (
        <Loading label="Signing you in…" rows={1} />
      )}
    </main>
  );
}
