import { Suspense } from "react";
import { OnboardingFlow } from "@/components/connect/onboarding-flow";
import { RequireAuth } from "@/components/layout/require-auth";
import { Loading } from "@/components/states/states";

// Protected, without the app navigation (S31). Suspense: the flow reads ?reconnect= from the URL.
export default function OnboardingPage() {
  return (
    <RequireAuth>
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-10 sm:py-16">
        <Suspense fallback={<Loading label="Loading…" rows={3} />}>
          <OnboardingFlow />
        </Suspense>
      </main>
    </RequireAuth>
  );
}
