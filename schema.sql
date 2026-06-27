-- Run this in Supabase SQL editor.
-- Assumes Supabase Auth is enabled (auth.users table exists).

-- If you already ran this schema before (table exists without `caption`),
-- run this single line first, then the rest is safe to skip/re-run:
-- alter table scripts add column if not exists caption text;

create table if not exists chapters (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    month_label text not null,          -- e.g. '2026-06'
    total_days int not null,            -- days in that month
    completed_days int not null default 0,
    status text not null default 'active', -- active | completed | failed
    created_at timestamptz not null default now(),
    unique(user_id, month_label)
);

create table if not exists scripts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    topic text not null,
    hook text,
    body text,
    cta text,
    caption text,
    status text not null default 'draft', -- draft | shot | posted | discarded
    created_at timestamptz not null default now(),
    shot_at timestamptz,
    posted_at timestamptz
);

create table if not exists progress (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    chapter_id uuid references chapters(id) on delete cascade,
    log_date date not null,
    action_taken boolean not null default false,
    script_id uuid references scripts(id),
    created_at timestamptz not null default now(),
    unique(user_id, log_date)
);

-- Row Level Security
alter table chapters enable row level security;
alter table scripts enable row level security;
alter table progress enable row level security;

create policy "own chapters" on chapters
    for all using (auth.uid() = user_id);
create policy "own scripts" on scripts
    for all using (auth.uid() = user_id);
create policy "own progress" on progress
    for all using (auth.uid() = user_id);

-- ---------- instagram integration ----------

create table if not exists instagram_accounts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade unique,
    ig_business_id text not null,
    ig_username text,
    page_id text not null,
    access_token text not null,
    token_expires_at timestamptz,
    connected_at timestamptz not null default now()
);

create table if not exists scheduled_posts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    script_id uuid references scripts(id),
    caption text not null,
    video_url text not null,
    scheduled_for timestamptz not null,
    status text not null default 'pending', -- pending | publishing | published | failed | canceled
    error text,
    ig_media_id text,
    created_at timestamptz not null default now(),
    published_at timestamptz
);

alter table instagram_accounts enable row level security;
alter table scheduled_posts enable row level security;

create policy "own instagram account" on instagram_accounts
    for all using (auth.uid() = user_id);
create policy "own scheduled posts" on scheduled_posts
    for all using (auth.uid() = user_id);
