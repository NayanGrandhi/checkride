"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function LoadButton() {
  const router = useRouter();
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [message, setMessage] = useState("");

  async function load() {
    setState("loading");
    setMessage("");
    try {
      const res = await fetch("/api/admin/load-library", { method: "POST" });
      const body = await res.json();
      if (!res.ok || !body.ok) throw new Error(body.error ?? `Server returned ${res.status}`);
      setState("done");
      setMessage(`Loaded ${body.passages.toLocaleString()} passages from ${body.documents} documents.`);
      router.refresh();
    } catch (e) {
      setState("error");
      setMessage(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={load}
        disabled={state === "loading"}
        className="h-12 rounded-xl bg-airspace px-5 font-display font-bold text-white disabled:opacity-60"
      >
        {state === "loading" ? "Loading the library… (up to a minute)" : "Load FAA library"}
      </button>
      {message && (
        <p role="status" className={state === "error" ? "text-unsat" : "text-sat"}>
          {message}
        </p>
      )}
    </div>
  );
}
