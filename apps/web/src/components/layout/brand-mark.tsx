import { GraduationCap } from "lucide-react";
import { cn } from "@/lib/utils";

/** Product wordmark (S35). Deliberately not a UMass logo: this is a student hackathon project. */
export function BrandMark({ size = "md", className }: { size?: "sm" | "md"; className?: string }) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <span
        className={cn(
          "grid shrink-0 place-items-center rounded-lg bg-white/15 ring-1 ring-white/25",
          size === "sm" ? "size-7" : "size-9",
        )}
        aria-hidden
      >
        <GraduationCap className={size === "sm" ? "size-4" : "size-5"} />
      </span>
      <span className="flex flex-col leading-tight">
        <span className={cn("font-display font-semibold tracking-tight", size === "sm" ? "text-base" : "text-lg")}>
          LMS Agent
        </span>
        <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-white/70">for UMass students</span>
      </span>
    </span>
  );
}
