import { RequireAuth } from "@/components/layout/require-auth";
import { Placeholder } from "@/components/states/placeholder";

// Protected, without the app navigation. The connect flow itself is S31 (Stage 2).
export default function OnboardingPage() {
  return (
    <RequireAuth>
      <main className="flex-1 px-4 py-16">
        <Placeholder title="Connect your classes" />
      </main>
    </RequireAuth>
  );
}
