import { redirect } from "next/navigation";

// S36: the Study list moved into Sessions; /study/[id] still opens a study set.
export default function StudyPage() {
  redirect("/sessions");
}
