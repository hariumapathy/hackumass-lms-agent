"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { Loading } from "@/components/states/states";
import { useAuth } from "@/lib/auth/auth-context";

/** Protected routes: signed-out visitors go to "/" (S30 rule 2). */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "signed_out") router.replace("/");
  }, [status, router]);

  if (status !== "signed_in") {
    return (
      <div className="mx-auto w-full max-w-3xl px-4">
        <Loading label="Checking your sign-in…" />
      </div>
    );
  }
  return <>{children}</>;
}
