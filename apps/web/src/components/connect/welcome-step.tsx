import { ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";

/** S31 step 1: what we do + the privacy promise. */
export function WelcomeStep({ onStart }: { onStart: () => void }) {
  return (
    <section aria-labelledby="welcome-heading" className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <h1 id="welcome-heading" className="text-3xl font-semibold tracking-tight">
          Your classes, all in one place
        </h1>
        <p className="text-lg text-muted-foreground">
          We bring your Canvas, Gradescope and Echo360 deadlines, slides and lectures together. See what&apos;s due
          today, ask questions about your classes, and get study plans with links back to the source.
        </p>
      </div>
      <div className="flex gap-3 rounded-lg border bg-muted/30 p-4 text-sm">
        <ShieldCheck className="mt-0.5 size-5 shrink-0 text-green-700 dark:text-green-400" aria-hidden />
        <p>
          We only read your class information. We never see your UMass password, and we never submit or change
          anything for you.
        </p>
      </div>
      <div className="flex flex-col gap-2">
        <Button size="lg" className="w-fit" onClick={onStart}>
          Get started
        </Button>
        <p className="text-sm text-muted-foreground">Setup takes about 3 minutes.</p>
      </div>
    </section>
  );
}
