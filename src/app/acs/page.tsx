import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { connection } from "next/server";
import { Disclaimer } from "@/components/Disclaimer";
import { getPublicSupabase } from "@/lib/supabase";

export const metadata: Metadata = { title: "ACS browser · checkride" };

type Element = { code: string; type: string; text: string; parent_code: string | null; sort: number };
type Task = {
  code: string;
  name: string;
  sort: number;
  classes: string[];
  objective: string;
  references_text: string;
  acs_elements: Element[];
};
type Area = { numeral: string; name: string; sort: number; acs_tasks: Task[] };

const TYPE_LABELS: Record<string, string> = {
  knowledge: "Knowledge",
  risk_management: "Risk management",
  skill: "Skills",
};

async function loadAcs() {
  const supabase = getPublicSupabase();
  if (!supabase) return { error: "not-connected" as const };

  const [{ data: cert }, { data: areas, error }] = await Promise.all([
    supabase.from("certificates").select("name, acs_document").eq("code", "PA").single(),
    supabase
      .from("acs_areas")
      .select(
        "numeral, name, sort, acs_tasks(code, name, sort, classes, objective, references_text, acs_elements(code, type, text, parent_code, sort))",
      )
      .order("sort"),
  ]);
  if (error || !areas) return { error: "query-failed" as const };

  const sorted = (areas as Area[]).map((a) => ({
    ...a,
    acs_tasks: [...a.acs_tasks]
      .sort((x, y) => x.sort - y.sort)
      .map((t) => ({ ...t, acs_elements: [...t.acs_elements].sort((x, y) => x.sort - y.sort) })),
  }));
  return { cert, areas: sorted };
}

export default function AcsPage() {
  // The page frame renders instantly; the ACS streams in from the database.
  return (
    <Shell>
      <Suspense fallback={<p className="text-ink-muted">Loading the ACS…</p>}>
        <AcsContent />
      </Suspense>
    </Shell>
  );
}

async function AcsContent() {
  await connection(); // always read fresh from the database
  const result = await loadAcs();

  if ("error" in result) {
    return (
        <p className="rounded-xl bg-work-bg px-4 py-3 text-work">
          {result.error === "not-connected"
            ? "The database isn't connected to the site yet. Add the two Supabase settings in Vercel, then redeploy."
            : "Couldn't read the ACS from the database. Check that the Supabase project is running (free projects pause after a week without use)."}
        </p>
    );
  }

  const { cert, areas } = result;
  const nTasks = areas.reduce((n, a) => n + a.acs_tasks.length, 0);
  const nElements = areas.reduce((n, a) => n + a.acs_tasks.reduce((m, t) => m + t.acs_elements.length, 0), 0);

  return (
    <>
      <p className="text-base leading-relaxed text-ink-soft">
        {cert?.name ?? "Private Pilot - Airplane"}, {cert?.acs_document ?? "FAA-S-ACS-6C"}.{" "}
        {areas.length} areas, {nTasks} tasks, {nElements.toLocaleString()} elements.
      </p>

      <ol className="flex flex-col gap-3">
        {areas.map((area) => (
          <li key={area.numeral}>
            <details className="group rounded-2xl bg-panel open:bg-white">
              <summary className="flex min-h-14 cursor-pointer list-none items-center gap-3 px-4 py-3">
                <span className="w-10 shrink-0 font-display text-sm font-bold text-course">{area.numeral}</span>
                <span className="flex-1 font-bold">{area.name}</span>
                <span className="text-sm text-ink-muted">{area.acs_tasks.length} tasks</span>
              </summary>
              <ol className="flex flex-col gap-2 px-3 pb-3">
                {area.acs_tasks.map((task) => (
                  <li key={task.code}>
                    <TaskView task={task} />
                  </li>
                ))}
              </ol>
            </details>
          </li>
        ))}
      </ol>
    </>
  );
}

function TaskView({ task }: { task: Task }) {
  const groups = ["knowledge", "risk_management", "skill"].map((type) => ({
    type,
    items: task.acs_elements.filter((e) => e.type === type),
  }));

  return (
    <details className="rounded-xl border border-line">
      <summary className="flex min-h-12 cursor-pointer list-none items-center gap-3 px-3 py-2">
        <span className="w-16 shrink-0 font-display text-[13px] font-bold text-terrain-ink">{task.code}</span>
        <span className="flex-1">{task.name}</span>
      </summary>
      <div className="flex flex-col gap-4 px-3 pb-4">
        <p className="text-[15px] leading-relaxed text-ink-soft">{task.objective}</p>
        <p className="text-[13px] text-ink-muted">References: {task.references_text}</p>
        {groups.map(
          (g) =>
            g.items.length > 0 && (
              <section key={g.type} className="flex flex-col gap-2">
                <h3 className="text-sm font-bold text-ink-soft">{TYPE_LABELS[g.type]}</h3>
                <ul className="flex flex-col gap-1.5">
                  {g.items.map((e) => (
                    <li key={e.code} className={`flex gap-3 text-[15px] leading-snug ${e.parent_code ? "pl-6" : ""}`}>
                      <span className="w-24 shrink-0 font-display text-[12.5px] text-ink-muted">{e.code}</span>
                      <span>{e.text}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ),
        )}
      </div>
    </details>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-5 pt-5 pb-8">
      <header className="flex items-center justify-between">
        <Link href="/" className="font-display text-lg font-bold tracking-wide text-ink no-underline">
          checkride
        </Link>
      </header>
      <h1 className="font-display text-[28px] font-bold leading-tight">ACS browser</h1>
      {children}
      <div className="flex-1" />
      <Disclaimer />
    </main>
  );
}
