import { Disclaimer } from "@/components/Disclaimer";

// Step 1a placeholder. Replaced by the real "Start practice" screen in step 1d.
export default function Home() {
  return (
    <main className="relative mx-auto flex w-full max-w-md flex-1 flex-col gap-6 overflow-hidden px-5 pt-5 pb-6">
      {/* Airspace rings, a nod to sectional charts. Decorative only. */}
      <svg
        aria-hidden="true"
        width="320"
        height="320"
        viewBox="0 0 320 320"
        className="pointer-events-none absolute -top-44 -right-48 opacity-40"
      >
        <circle cx="160" cy="160" r="150" fill="none" stroke="#2456a6" strokeWidth="2" />
        <circle cx="160" cy="160" r="100" fill="none" stroke="#2456a6" strokeWidth="2" />
        <circle cx="160" cy="160" r="52" fill="none" stroke="#a3266f" strokeWidth="2" strokeDasharray="6 5" />
      </svg>

      <header className="relative font-display text-lg font-bold tracking-wide">checkride</header>

      <section className="relative flex flex-col gap-2 pt-4">
        <h1 className="font-display text-[30px] font-bold leading-tight">Cleared for setup.</h1>
        <p className="text-base leading-relaxed text-ink-soft">
          The project skeleton is live. Next we load the FAA standards and
          handbooks, then build the AI examiner.
        </p>
      </section>

      <div className="flex-1" />
      <Disclaimer />
    </main>
  );
}
