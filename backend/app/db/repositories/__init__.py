"""Repositories: all SQL lives here. Rule (S01/S20): every public function is
`fn(conn, user_id, ...)` and filters by `user_id` (the backend uses the service role, which
bypasses RLS). Enforced by test S20-T04."""
