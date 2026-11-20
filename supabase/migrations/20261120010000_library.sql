-- Step 1c: FAA reference library.
-- Public FAA documents split into short passages. Grading and the tutor may
-- only cite passages from here, quoting their exact words.

create table public.source_documents (
  id          text primary key,             -- 'phak', 'cfr91', ...
  short_name  text not null,                -- 'PHAK', '14 CFR Part 91'
  title       text not null,
  doc_number  text not null,                -- 'FAA-H-8083-25C' or edition note
  url         text not null,
  loaded_at   timestamptz not null default now()
);

create table public.source_passages (
  id           text primary key,            -- 'phak-00123'
  document_id  text not null references public.source_documents(id) on delete cascade,
  locator      text not null,               -- how to cite it: 'PHAK Ch. 11, p. 11-14', '14 CFR § 91.151'
  page_label   text,
  section      text not null default '',    -- chapter / section / paragraph title
  content      text not null,
  -- keyword search: the section title counts more than body text
  tsv          tsvector generated always as (
                 setweight(to_tsvector('english', coalesce(section, '')), 'A') ||
                 setweight(to_tsvector('english', content), 'B')
               ) stored
);

create index source_passages_document_idx on public.source_passages (document_id);
create index source_passages_tsv_idx on public.source_passages using gin (tsv);

alter table public.source_documents enable row level security;
alter table public.source_passages  enable row level security;
create policy "Library is readable by everyone" on public.source_documents for select using (true);
create policy "Library is readable by everyone" on public.source_passages  for select using (true);
grant select on public.source_documents, public.source_passages to anon, authenticated;
-- the server (secret key) loads the library
grant select, insert, update, delete on public.source_documents, public.source_passages to service_role;

-- Keyword search. Any of the words may match, but passages containing all of
-- them rank much higher, and words in the section title count most
-- (weights: title 1.0, body 0.4). Tested against sample checkride questions:
-- "VFR fuel requirements" -> 14 CFR 91.151 first.
create or replace function public.search_passages(q text, k int default 8, doc text default null)
returns table (id text, document_id text, locator text, section text, content text, rank real)
language sql
stable
set search_path = public
as $$
  with query as (
    select plainto_tsquery('english', q) as q_all,
           to_tsquery('english', nullif(replace(plainto_tsquery('english', q)::text, ' & ', ' | '), '')) as q_any
  )
  select p.id, p.document_id, p.locator, p.section, p.content,
         ( ts_rank('{0.1, 0.2, 0.4, 1.0}', p.tsv, query.q_any, 1)
         + case when p.tsv @@ query.q_all then 3 * ts_rank('{0.1, 0.2, 0.4, 1.0}', p.tsv, query.q_all, 1) else 0 end
         )::real as rank
  from public.source_passages p, query
  where query.q_any is not null
    and p.tsv @@ query.q_any
    and (doc is null or p.document_id = doc)
  order by rank desc, p.id
  limit least(greatest(k, 1), 50);
$$;

grant execute on function public.search_passages(text, int, text) to anon, authenticated, service_role;
