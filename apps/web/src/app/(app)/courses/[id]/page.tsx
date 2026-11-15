"use client";

import { useParams } from "next/navigation";
import { CourseScreen } from "@/components/course/course-screen";

export default function CoursePage() {
  const { id } = useParams<{ id: string }>();
  return <CourseScreen key={id} courseId={id} />;
}
