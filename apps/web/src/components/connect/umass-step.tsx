"use client";

import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Me, Platform } from "@/lib/api/types";
import { PLATFORM_LABEL } from "@/lib/platforms";
import { LiveLogin } from "./live-login";
import { isConnected, LOGIN_PLATFORMS } from "./progress";

const WHY: Partial<Record<Platform, string>> = {
  gradescope: "Homework scores and Gradescope due dates",
  piazza: "Class Q&A, so you can ask what your professor or TAs answered",
};

interface Props {
  me: Me;
  pollMs?: number;
  onConnected: (platform: Platform) => void;
  onNext: () => void;
}

/** S31 step 3: optional logins for Gradescope and Piazza. */
export function UmassStep({ me, pollMs, onConnected, onNext }: Props) {
  const anyConnected = LOGIN_PLATFORMS.some((p) => isConnected(me, p));
  return (
    <section aria-labelledby="umass-step-heading" className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 id="umass-step-heading" className="text-2xl font-semibold tracking-tight">
          Connect Gradescope and Piazza
        </h1>
        <p className="text-muted-foreground">
          Optional. Log in once and we&apos;ll stay logged in for you. We never see your password.
        </p>
      </div>

      <ul className="flex flex-col gap-3">
        {LOGIN_PLATFORMS.map((p) => (
          <li key={p} className="flex flex-col gap-3 rounded-lg border p-4">
            <div>
              <p className="font-medium">{PLATFORM_LABEL[p]}</p>
              <p className="text-sm text-muted-foreground">{WHY[p]}</p>
            </div>
            {isConnected(me, p) ? (
              <p className="inline-flex items-center gap-2 font-medium text-green-700 dark:text-green-400">
                <CheckCircle2 className="size-4" aria-hidden /> {PLATFORM_LABEL[p]} connected
              </p>
            ) : (
              <LiveLogin platform={p} pollMs={pollMs} onConnected={() => onConnected(p)} />
            )}
          </li>
        ))}
      </ul>
      <p className="text-sm text-muted-foreground">The login window opens on a laptop, so do this step there.</p>

      <Button size="lg" variant={anyConnected ? "default" : "outline"} className="w-fit" onClick={onNext}>
        {anyConnected ? "Continue" : "Skip for now"}
      </Button>
    </section>
  );
}
