"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ErrorState, Loading } from "@/components/states/states";
import { api } from "@/lib/api/client";
import type { Platform } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/auth-context";
import { PLATFORM_LABEL } from "@/lib/platforms";
import { CalendarStep } from "./calendar-step";
import { CanvasStep } from "./canvas-step";
import { FinishingStep } from "./finishing-step";
import { LiveLogin } from "./live-login";
import {
  firstIncompleteStep,
  isConnected,
  loadProgress,
  LOGIN_PLATFORMS,
  saveProgress,
  STEPS,
  type OnboardingProgress,
  type Step,
} from "./progress";
import { UmassStep } from "./umass-step";
import { WelcomeStep } from "./welcome-step";

const RECONNECTABLE: Platform[] = ["canvas", ...LOGIN_PLATFORMS];

function parseReconnect(value: string | null): Platform | null {
  return RECONNECTABLE.find((p) => p === value) ?? null;
}

interface Props {
  loginPollMs?: number;
  statusPollMs?: number;
}

/** S31 onboarding: Welcome → Canvas → UMass logins → Calendar → Getting your classes. */
export function OnboardingFlow({ loginPollMs, statusPollMs }: Props) {
  const params = useSearchParams();
  const reconnect = parseReconnect(params.get("reconnect"));
  return reconnect ? (
    <ReconnectView platform={reconnect} pollMs={loginPollMs} />
  ) : (
    <Steps loginPollMs={loginPollMs} statusPollMs={statusPollMs} />
  );
}

function Steps({ loginPollMs, statusPollMs }: Props) {
  const { user } = useAuth();
  const userId = user?.id ?? "anonymous";
  const router = useRouter();
  const qc = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api().me() });
  const [progress, setProgress] = useState<OnboardingProgress>(() => loadProgress(userId));
  // Null until the student acts: then the step is pinned so a /me refetch can't skip a screen.
  const [pinned, setPinned] = useState<Step | null>(null);

  const update = (patch: OnboardingProgress) => {
    const next = { ...progress, ...patch };
    saveProgress(userId, next);
    setProgress(next);
  };
  const refreshMe = () => void qc.invalidateQueries({ queryKey: ["me"] });

  if (me.isPending) return <Loading label="Loading…" rows={3} />;
  if (me.isError) return <ErrorState error={me.error} onRetry={() => void me.refetch()} />;

  const step = pinned ?? firstIncompleteStep(me.data, progress);

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm font-medium text-muted-foreground">
        Step {STEPS.indexOf(step) + 1} of {STEPS.length}
      </p>
      {step === "welcome" && (
        <WelcomeStep
          onStart={() => {
            update({ welcomed: true });
            setPinned("canvas");
          }}
        />
      )}
      {step === "canvas" && (
        <CanvasStep
          onLinked={() => {
            setPinned("canvas");
            refreshMe();
          }}
          onContinue={() => setPinned("umass")}
        />
      )}
      {step === "umass" && (
        <UmassStep
          me={me.data}
          pollMs={loginPollMs}
          onConnected={() => {
            setPinned("umass");
            refreshMe();
          }}
          onNext={() => {
            update({ skipped: LOGIN_PLATFORMS.filter((p) => !isConnected(me.data, p)) });
            setPinned("calendar");
          }}
        />
      )}
      {step === "calendar" && (
        <CalendarStep
          onDone={(calendar) => {
            update({ calendar });
            setPinned("finishing");
          }}
        />
      )}
      {step === "finishing" && (
        <FinishingStep
          pollMs={statusPollMs}
          onDone={() => {
            for (const key of ["me", "today", "courses"]) void qc.invalidateQueries({ queryKey: [key] });
            router.push("/today");
          }}
        />
      )}
    </div>
  );
}

/** `?reconnect=<platform>` (S31 rule 6): just that platform's step, then back to Settings. */
function ReconnectView({ platform, pollMs }: { platform: Platform; pollMs?: number }) {
  const router = useRouter();
  const qc = useQueryClient();
  const label = PLATFORM_LABEL[platform];
  const me = useQuery({ queryKey: ["me"], queryFn: () => api().me() });
  // First-time connect vs. reconnect: same screen, different words (Settings links here for both).
  const fresh = me.data ? !me.data.connections.some((c) => c.platform === platform) : false;
  const verb = fresh ? "Connect" : "Reconnect";
  const done = () => {
    for (const key of ["me", "today", "courses", "course", "sync-status"]) void qc.invalidateQueries({ queryKey: [key] });
    router.push("/settings");
  };

  return (
    <div className="flex flex-col gap-6">
      <Link href="/settings" className="w-fit text-sm text-muted-foreground underline">
        Back to settings
      </Link>
      {platform === "canvas" ? (
        <CanvasStep heading={`${verb} Canvas`} onLinked={done} />
      ) : (
        <section aria-labelledby="reconnect-heading" className="flex flex-col gap-4">
          <h1 id="reconnect-heading" className="text-2xl font-semibold tracking-tight">
            {verb} {label}
          </h1>
          <p className="text-muted-foreground">
            {fresh
              ? `Log in to ${label} so we can bring in your classes. We never see your password.`
              : `Log in to ${label} again so we can keep your classes up to date. We never see your password.`}
          </p>
          <LiveLogin platform={platform} pollMs={pollMs} onConnected={done} />
        </section>
      )}
    </div>
  );
}
