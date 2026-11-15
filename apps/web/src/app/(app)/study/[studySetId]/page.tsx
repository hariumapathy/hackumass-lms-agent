"use client";
import { useParams } from "next/navigation";
import { StudyDetail } from "@/components/study/study-screen";

export default function StudySetPage() {
  const { studySetId } = useParams<{ studySetId: string }>();
  return <StudyDetail id={studySetId} />;
}