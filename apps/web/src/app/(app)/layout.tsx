import { AppShell } from "@/components/layout/app-shell";
import { RequireAuth } from "@/components/layout/require-auth";

// Signed-in screens wait for the browser-side session check (S30 rule 2), so navigations into this
// layout may block on purpose. Opt out of Next 16's dev-only instant-navigation validation for it.
export const instant = false;

// Every signed-in screen with navigation (S30 route table).
export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <RequireAuth>
      <AppShell>{children}</AppShell>
    </RequireAuth>
  );
}
