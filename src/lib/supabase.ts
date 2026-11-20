import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/**
 * Read-only Supabase client using the public (publishable) key.
 * Safe for public data like the ACS. Row Level Security in the database
 * decides what this key may read.
 *
 * Returns null when the environment variables aren't set yet, so pages can
 * show a friendly "not connected" message instead of crashing.
 */
export function getPublicSupabase(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) return null;
  return createClient(url, key, { auth: { persistSession: false } });
}
