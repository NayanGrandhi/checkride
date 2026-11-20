import { readFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import { getAdminSupabase } from "@/lib/supabase-admin";

// Loads the FAA library (data/library, built by scripts/build_library.py)
// into Supabase. Safe to run repeatedly: rows are upserted by id, and any
// passages no longer in the files are removed.
export const maxDuration = 60;

type Passage = {
  id: string;
  document_id: string;
  locator: string;
  page_label: string | null;
  section: string;
  content: string;
};

export async function POST() {
  const supabase = getAdminSupabase();
  if (!supabase) {
    return Response.json({ ok: false, error: "Supabase secret key is not configured on the server." }, { status: 500 });
  }

  const dir = path.join(process.cwd(), "data", "library");
  const documents = JSON.parse(await readFile(path.join(dir, "documents.json"), "utf8"));
  const passages: Passage[] = gunzipSync(await readFile(path.join(dir, "passages.jsonl.gz")))
    .toString("utf8")
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line));

  const docResult = await supabase.from("source_documents").upsert(documents, { onConflict: "id" });
  if (docResult.error) return Response.json({ ok: false, error: docResult.error.message }, { status: 500 });

  const BATCH = 500;
  for (let i = 0; i < passages.length; i += BATCH) {
    const { error } = await supabase
      .from("source_passages")
      .upsert(passages.slice(i, i + BATCH), { onConflict: "id" });
    if (error) {
      return Response.json({ ok: false, error: error.message, loadedSoFar: i }, { status: 500 });
    }
  }

  // Remove passages that were in an older build but not this one.
  const keep = new Set(passages.map((p) => p.id));
  const { data: existing } = await supabase.from("source_passages").select("id").limit(20000);
  const stale = (existing ?? []).map((r) => r.id as string).filter((id) => !keep.has(id));
  for (let i = 0; i < stale.length; i += BATCH) {
    await supabase.from("source_passages").delete().in("id", stale.slice(i, i + BATCH));
  }

  return Response.json({ ok: true, documents: documents.length, passages: passages.length, removed: stale.length });
}
