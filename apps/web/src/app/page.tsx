import { SignInPanel } from "@/components/auth/sign-in-panel";

// Landing + sign in (S30). Signed-in visitors are sent on by SignInPanel.
export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-6 px-4 py-24">
      <div className="flex flex-col gap-4">
        <h1 className="text-4xl font-semibold tracking-tight">HackUMass LMS Agent</h1>
        <p className="text-lg text-muted-foreground">
          One login, every class. Your AI study partner that already knows your Canvas, Gradescope and lectures.
        </p>
      </div>
      <SignInPanel />
    </main>
  );
}
