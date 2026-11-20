-- Step 1b: ACS content tables.
-- The ACS (Airman Certification Standards) is the FAA's list of everything a
-- checkride can test: certificate -> areas of operation -> tasks -> elements.
-- Adding a new certificate (Instrument, Commercial...) is just new rows here.

create table public.certificates (
  id            uuid primary key default gen_random_uuid(),
  code          text not null unique,          -- ACS code prefix, e.g. 'PA'
  name          text not null,                 -- 'Private Pilot - Airplane'
  acs_document  text not null,                 -- 'FAA-S-ACS-6C'
  created_at    timestamptz not null default now()
);

create table public.acs_areas (
  id              uuid primary key default gen_random_uuid(),
  certificate_id  uuid not null references public.certificates(id) on delete cascade,
  numeral         text not null,               -- 'I', 'II', ...
  name            text not null,
  sort            int  not null,
  unique (certificate_id, numeral)
);

create table public.acs_tasks (
  id               uuid primary key default gen_random_uuid(),
  area_id          uuid not null references public.acs_areas(id) on delete cascade,
  letter           text not null,
  code             text not null unique,       -- 'PA.I.B'
  name             text not null,
  classes          text[] not null default '{}', -- empty = all classes; else ASEL/AMEL/ASES/AMES
  references_text  text not null default '',
  objective        text not null default '',
  notes            text[] not null default '{}',
  sort             int  not null
);

create table public.acs_elements (
  id           uuid primary key default gen_random_uuid(),
  task_id      uuid not null references public.acs_tasks(id) on delete cascade,
  code         text not null unique,           -- 'PA.I.B.K1a'
  type         text not null check (type in ('knowledge', 'risk_management', 'skill')),
  text         text not null,
  parent_code  text,                           -- 'PA.I.B.K1' for sub-element K1a
  sort         int  not null
);

create index on public.acs_areas (certificate_id);
create index on public.acs_tasks (area_id);
create index on public.acs_elements (task_id);

-- ACS content is public FAA material: anyone may read it, nobody may change it
-- through the public API. Changes happen only through load_acs() below.
alter table public.certificates enable row level security;
alter table public.acs_areas    enable row level security;
alter table public.acs_tasks    enable row level security;
alter table public.acs_elements enable row level security;

create policy "ACS content is readable by everyone" on public.certificates for select using (true);
create policy "ACS content is readable by everyone" on public.acs_areas    for select using (true);
create policy "ACS content is readable by everyone" on public.acs_tasks    for select using (true);
create policy "ACS content is readable by everyone" on public.acs_elements for select using (true);

grant select on public.certificates, public.acs_areas, public.acs_tasks, public.acs_elements
  to anon, authenticated;

-- Load (or reload) one certificate from the JSON produced by scripts/parse_acs.py.
-- Re-running replaces that certificate's areas/tasks/elements.
create or replace function public.load_acs(doc jsonb)
returns text
language plpgsql
set search_path = public
as $$
declare
  cert_id uuid;
  a jsonb; t jsonb; e jsonb;
  area_id uuid; task_id uuid;
  ai int := 0; ti int; ei int;
  n_tasks int := 0; n_elems int := 0;
begin
  insert into certificates (code, name, acs_document)
  values (doc->'certificate'->>'code', doc->'certificate'->>'name', doc->'certificate'->>'acs_document')
  on conflict (code) do update set name = excluded.name, acs_document = excluded.acs_document
  returning id into cert_id;

  delete from acs_areas where certificate_id = cert_id;  -- cascades to tasks/elements

  for a in select * from jsonb_array_elements(doc->'areas') loop
    ai := ai + 1;
    insert into acs_areas (certificate_id, numeral, name, sort)
    values (cert_id, a->>'numeral', a->>'name', ai)
    returning id into area_id;

    ti := 0;
    for t in select * from jsonb_array_elements(a->'tasks') loop
      ti := ti + 1; n_tasks := n_tasks + 1;
      insert into acs_tasks (area_id, letter, code, name, classes, references_text, objective, notes, sort)
      values (
        area_id, t->>'letter', t->>'code', t->>'name',
        array(select jsonb_array_elements_text(t->'classes')),
        t->>'references', t->>'objective',
        array(select jsonb_array_elements_text(t->'notes')),
        ti)
      returning id into task_id;

      ei := 0;
      for e in select * from jsonb_array_elements(t->'elements') loop
        ei := ei + 1; n_elems := n_elems + 1;
        insert into acs_elements (task_id, code, type, text, parent_code, sort)
        values (task_id, e->>'code', e->>'type', e->>'text', e->>'parent', ei);
      end loop;
    end loop;
  end loop;

  return format('%s: %s areas, %s tasks, %s elements', doc->'certificate'->>'acs_document', ai, n_tasks, n_elems);
end;
$$;

-- Only the database owner may load content.
revoke execute on function public.load_acs(jsonb) from public, anon, authenticated;
