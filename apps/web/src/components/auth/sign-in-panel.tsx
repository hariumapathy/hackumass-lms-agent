"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth/auth-context";

export function SignInPanel() {
  const auth = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Signed in (already, or just now via demo): the callback route picks /onboarding or /today.
  useEffect(() => {
    if (auth.status === "signed_in") router.replace("/auth/callback");
  }, [auth.status, router]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign-in failed. Try again.");
    } finally {
      setBusy(false);
    }
  };

  if (auth.mode === "demo") {
    return (
      <div className="flex flex-col items-start gap-2">
        <Button
          size="lg"
          disabled={busy || auth.status === "loading"}
          onClick={() => run(auth.signInDemo)}
        >
          Continue with demo data
        </Button>
        <p className="text-sm text-muted-foreground">Demo mode: explore with a sample UMass semester.</p>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      </div>
    );
  }

  const onEmail = (e: FormEvent) => {
    e.preventDefault();
    void run(async () => {
      await auth.signInWithEmail(email.trim());
      setSent(true);
    });
  };

  return (
    <div className="flex max-w-sm flex-col gap-4">
      <Button size="lg" disabled={busy} onClick={() => run(auth.signInWithGoogle)}>
        Continue with Google
      </Button>
      <div className="text-center text-xs uppercase text-muted-foreground">or</div>
      {sent ? (
        <p role="status" className="text-sm">
          Check {email} for a sign-in link.
        </p>
      ) : (
        <form onSubmit={onEmail} className="flex gap-2">
          <label htmlFor="email" className="sr-only">
            Email
          </label>
          <Input
            id="email"
            type="email"
            required
            autoComplete="email"
            placeholder="you@umass.edu"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button type="submit" variant="outline" disabled={busy}>
            Email me a link
          </Button>
        </form>
      )}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
