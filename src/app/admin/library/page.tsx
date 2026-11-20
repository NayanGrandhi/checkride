import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";
import { getPublicSupabase } from "@/lib/supabase";
import { LoadButton } from "./LoadButton";

export const metadata: Metadata = { title: "FAA library · checkride admin" };

type Hit = { id: string; document_id: string; locator: string; section: string; content: string; rank: number };

export default function LibraryPage(props: PageProps<"/admin/library">) {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-5 pt-5 pb-8">
      <header className="flex items-center justify-between">
        <Link href="/" className="font-display text-lg font-bold tracking-wide text-ink no-underline">
          checkride
        </Link>
        <span className="text-sm text-ink-muted">Admin</span>
      </header>
      <h1 className="font-display text-[28px] font-bold leading-tight">FAA library</h1>
      <p className="text-ink-soft">
        Official FAA documents, split into short passages. The examiner may only cite text that exists here.
      </p>

      <Suspense fallback={<p className="text-ink-muted">Checking the library…</p>}>
        <Status />
      </Suspense>

      <LoadButton />

      <section className="flex flex-col gap-3 border-t border-line pt-6">
        <h2 className="font-display text-xl font-bold">Test a search</h2>
        <form className="flex gap-2" action="/admin/library">
          <label className="sr-only" htmlFor="q">Search the FAA library</label>
          <input
            id="q"
            name="q"
            placeholder="e.g. VFR fuel requirements"
            className="h-12 min-w-0 flex-1 rounded-xl border border-line bg-white px-4"
          />
          <button type="submit" className="h-12 rounded-xl border border-line bg-white px-4 font-bold">
            Search
          </button>
        </form>
        <Suspense fallback={null}>
          <Results searchParams={props.searchParams} />
        </Suspense>
      </section>
    </main>
  );
}

async function Status() {
  await connection();
  const supabase = getPublicSupabase();
  if (!supabase) return <Notice>The database isn&apos;t connected to the site yet.</Notice>;

  const { data: docs, error } = await supabase.from("source_documents").select("id, short_name, doc_number").order("id");
  if (error) return <Notice>Couldn&apos;t read the library ({error.message}). Has the library table been created?</Notice>;
  if (!docs?.length) return <Notice>The library is empty. Press “Load FAA library”.</Notice>;

  const counts = await Promise.all(
    docs.map(async (d) => {
      const { count } = await supabase
        .from("source_passages")
        .select("id", { count: "exact", head: true })
        .eq("document_id", d.id);
      return count ?? 0;
    }),
  );
  const total = counts.reduce((a, b) => a + b, 0);

  return (
    <div className="rounded-2xl bg-panel p-4">
      <p className="mb-3 font-bold">{total.toLocaleString()} passages loaded</p>
      <ul className="flex flex-col gap-1.5 text-[15px]">
        {docs.map((d, i) => (
          <li key={d.id} className="flex justify-between gap-3">
            <span>
              {d.short_name} <span className="text-ink-muted">({d.doc_number})</span>
            </span>
            <span className="font-display text-sm">{counts[i].toLocaleString()}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

async function Results({ searchParams }: { searchParams: PageProps<"/admin/library">["searchParams"] }) {
  const q = (await searchParams).q;
  const query = typeof q === "string" ? q.trim() : "";
  if (!query) return null;

  await connection();
  const supabase = getPublicSupabase();
  if (!supabase) return null;
  const { data, error } = await supabase.rpc("search_passages", { q: query, k: 8 });
  if (error) return <Notice>Search failed: {error.message}</Notice>;
  const hits = (data ?? []) as Hit[];
  if (!hits.length) return <p className="text-ink-muted">No passages matched “{query}”.</p>;

  return (
    <ol className="flex flex-col gap-3">
      {hits.map((h) => (
        <li key={h.id} className="rounded-xl bg-white p-4">
          <p className="font-display text-sm font-bold text-airspace">{h.locator}</p>
          {h.section && <p className="text-sm text-ink-muted">{h.section}</p>}
          <p className="mt-2 text-[15px] leading-relaxed whitespace-pre-line">
            {h.content.length > 600 ? h.content.slice(0, 600) + "…" : h.content}
          </p>
        </li>
      ))}
    </ol>
  );
}

function Notice({ children }: { children: React.ReactNode }) {
  return <p className="rounded-xl bg-work-bg px-4 py-3 text-work">{children}</p>;
}
