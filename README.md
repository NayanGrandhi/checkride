# checkride (working name)

AI checkride prep for pilots. Phase 1: a text-only Private Pilot mock oral
exam, graded against the FAA Airman Certification Standards (FAA-S-ACS-6C),
with citations to official FAA sources and a debrief.

> Practice tool only. Not FAA-approved, and not a substitute for an
> instructor, a real checkride or the aircraft's POH.

## Stack

- Next.js (App Router) + TypeScript + Tailwind CSS v4
- Supabase: Postgres, auth, storage, pgvector (from step 1b)
- Claude API: examiner, grading, tutor (from step 1d)
- Voyage AI: embeddings for FAA document search (from step 1c)
- Hosted on Vercel

## Run it locally

```bash
npm install
npm run dev      # http://localhost:3000
npm run build    # production build check
npm run lint
```

## Layout

```
src/app/            pages and API routes (Next.js App Router)
src/components/     shared UI pieces (e.g. Disclaimer)
src/fonts/          bundled fonts (SIL Open Font License)
src/app/globals.css design tokens (colors, fonts)
```

## Design system ("sectional chart")

Colors are borrowed from FAA sectional charts and live as Tailwind tokens
in `src/app/globals.css`:

| Token | Use |
|---|---|
| `chart` | page background |
| `ink`, `ink-soft`, `ink-muted` | text |
| `airspace` | primary buttons and links |
| `course` (magenta) | the debrief route line only |
| `terrain` | the "current ACS task" strip |
| `sat`, `work`, `unsat` | grades, always with a text label |

Fonts: **B612** (Airbus cockpit typeface) for headings, scores and ACS
codes (`font-display`), **Atkinson Hyperlegible** for body text.

## Build phases

1. Text mock oral with ACS grading, citations and debrief  ← current
2. Voice, personas, scenario chains, live weather
3. Accounts, free tier, Stripe, progress, share cards (launch)
4. Study system
5. Document uploads
6. Instructor dashboard
7. Flight school admin
8. More certificates, then international
