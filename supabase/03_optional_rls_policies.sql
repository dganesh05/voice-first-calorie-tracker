-- Optional: enable RLS for direct client access patterns.
-- Your current backend uses service role credentials, so RLS does not block server-side writes.

alter table public.users enable row level security;
alter table public.personal_foods enable row level security;
alter table public.daily_logs enable row level security;
alter table public.global_foods enable row level security;

drop policy if exists users_select_own on public.users;
create policy users_select_own on public.users
for select
using (auth.uid() = id);

drop policy if exists users_update_own on public.users;
create policy users_update_own on public.users
for update
using (auth.uid() = id)
with check (auth.uid() = id);

drop policy if exists users_insert_own on public.users;
create policy users_insert_own on public.users
for insert
with check (auth.uid() = id);

drop policy if exists personal_foods_select_own on public.personal_foods;
create policy personal_foods_select_own on public.personal_foods
for select
using (auth.uid() = user_id);

drop policy if exists personal_foods_insert_own on public.personal_foods;
create policy personal_foods_insert_own on public.personal_foods
for insert
with check (auth.uid() = user_id);

drop policy if exists personal_foods_update_own on public.personal_foods;
create policy personal_foods_update_own on public.personal_foods
for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists daily_logs_select_own on public.daily_logs;
create policy daily_logs_select_own on public.daily_logs
for select
using (auth.uid() = user_id);

drop policy if exists daily_logs_insert_own on public.daily_logs;
create policy daily_logs_insert_own on public.daily_logs
for insert
with check (auth.uid() = user_id);

drop policy if exists global_foods_read_all on public.global_foods;
create policy global_foods_read_all on public.global_foods
for select
using (true);

drop policy if exists global_foods_insert_authenticated on public.global_foods;
create policy global_foods_insert_authenticated on public.global_foods
for insert
with check (auth.uid() is not null);
