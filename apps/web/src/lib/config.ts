// Public runtime config. Next.js inlines NEXT_PUBLIC_* at build/dev time.
export const config = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  apiMocks: process.env.NEXT_PUBLIC_API_MOCKS === "1",
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL || "",
  supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "",
  googleSignIn: process.env.NEXT_PUBLIC_GOOGLE_SIGN_IN_ENABLED === "1",
};

/** Supabase sign-in is used when configured; otherwise mock mode offers a demo sign-in. */
export const supabaseConfigured = () => Boolean(config.supabaseUrl && config.supabaseAnonKey);
