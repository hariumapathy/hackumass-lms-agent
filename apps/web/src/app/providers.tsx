"use client";

import type { ReactNode } from "react";
import { MockGate } from "@/components/states/mock-gate";
import { AuthProvider } from "@/lib/auth/auth-provider";

export function Providers({ children }: { children: ReactNode }) {
  return <MockGate><AuthProvider>{children}</AuthProvider></MockGate>;
}
