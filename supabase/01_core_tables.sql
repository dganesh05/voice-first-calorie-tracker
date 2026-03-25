-- Core schema for VoCalorie MVP.

create table if not exists public.users (
    id uuid primary key,
    email text not null unique,
    display_name text,
    daily_calorie_goal numeric(10,2) not null default 2000,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.personal_foods (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    food_name text not null,
    calories numeric(10,2) not null default 0,
    protein numeric(10,2) not null default 0,
    carbs numeric(10,2) not null default 0,
    fat numeric(10,2) not null default 0,
    brand text,
    descriptors text,
    source text not null default 'manual',
    created_at timestamptz not null default now()
);

create table if not exists public.global_foods (
    id uuid primary key default gen_random_uuid(),
    food_name text not null,
    calories numeric(10,2) not null default 0,
    protein numeric(10,2) not null default 0,
    carbs numeric(10,2) not null default 0,
    fat numeric(10,2) not null default 0,
    brand text,
    descriptors text,
    source text not null default 'crowdsourced',
    food_category text,
    created_at timestamptz not null default now()
);

create table if not exists public.daily_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    food_name text not null,
    calories numeric(10,2) not null default 0,
    protein numeric(10,2) not null default 0,
    carbs numeric(10,2) not null default 0,
    fat numeric(10,2) not null default 0,
    logged_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

-- Optional table used by /health/supabase and legacy /foods/search path.
create table if not exists public.food_searches (
    id bigserial primary key,
    food_name text not null,
    calories numeric(10,2) not null default 0,
    protein numeric(10,2) not null default 0,
    carbs numeric(10,2) not null default 0,
    fat numeric(10,2) not null default 0,
    created_at timestamptz not null default now()
);
