import { BookOpenCheck, CalendarCheck, MessageSquareQuote } from "lucide-react";
import { SignInPanel } from "@/components/auth/sign-in-panel";

const FEATURES = [
  { icon: CalendarCheck, title: "One Today view", text: "Canvas, Gradescope and Piazza deadlines in one list, with what changed." },
  { icon: MessageSquareQuote, title: "Answers with sources", text: "Ask about your classes. Every answer links the exact slide, post or page." },
  { icon: BookOpenCheck, title: "Study made for you", text: "Flashcards, quizzes and study sessions built from your own course materials." },
];

// Landing + sign in (S30, S35 look). Signed-in visitors are sent on by SignInPanel.
export default function Home() {
  return (
    <main className="flex min-h-dvh flex-1 flex-col lg:flex-row">
      <section className="relative isolate flex flex-col justify-between gap-6 overflow-hidden bg-maroon px-6 py-8 text-white sm:gap-10 sm:px-10 sm:py-10 lg:w-[55%] lg:py-14">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-24 -right-24 -z-10 size-96 rounded-full bg-white/5 blur-2xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-32 -left-16 -z-10 size-[28rem] rounded-full bg-black/20 blur-3xl"
        />
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/70">Built at HackUMass XIV</p>
        <div className="flex max-w-xl flex-col gap-5">
          <h1 className="text-4xl leading-[1.05] font-semibold sm:text-5xl">HackUMass LMS Agent</h1>
          <p className="text-lg text-white/85 sm:text-xl">
            One login, every class. Your AI study partner that already knows your Canvas, Gradescope and lectures.
          </p>
        </div>
        <ul className="hidden gap-5 sm:grid sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <li key={title} className="flex flex-col gap-2">
              <span className="grid size-9 place-items-center rounded-lg bg-white/12 ring-1 ring-white/20" aria-hidden>
                <Icon className="size-5 text-highlight" />
              </span>
              <span className="font-semibold">{title}</span>
              <span className="text-sm text-white/75">{text}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-1 items-start justify-center px-6 py-8 sm:items-center sm:px-10 sm:py-12">
        <div className="flex w-full max-w-sm flex-col gap-6">
          <div className="flex flex-col gap-1.5">
            <h2 className="font-display text-2xl font-semibold tracking-tight">Sign in</h2>
            <p className="text-sm text-muted-foreground">Use your email. We&apos;ll send you a one-time sign-in link, no password.</p>
          </div>
          <SignInPanel />
          <p className="text-xs leading-relaxed text-muted-foreground">
            A student project for UMass students. Not an official University of Massachusetts service. We never ask for
            your NetID password.
          </p>
        </div>
      </section>
    </main>
  );
}
