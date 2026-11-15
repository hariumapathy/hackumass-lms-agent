import type { CourseSummary } from "@/lib/api/types";

/** Split courses for navigation: ones with upcoming work first, the rest (past terms, quiet
 *  courses) folded away. Gradescope/Canvas imports can bring years of old classes. */
export function splitCourses(courses: CourseSummary[]): { active: CourseSummary[]; other: CourseSummary[] } {
  const active = courses.filter((c) => c.upcoming_count > 0);
  const other = courses.filter((c) => c.upcoming_count === 0);
  return { active, other };
}
