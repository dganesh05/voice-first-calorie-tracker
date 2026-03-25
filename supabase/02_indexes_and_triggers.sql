-- Query performance indexes.
create index if not exists idx_personal_foods_user_food
    on public.personal_foods (user_id, lower(food_name));

create index if not exists idx_global_foods_food
    on public.global_foods (lower(food_name));

create index if not exists idx_daily_logs_user_logged_at
    on public.daily_logs (user_id, logged_at);

-- Generic updated_at trigger function.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_users_set_updated_at on public.users;
create trigger trg_users_set_updated_at
before update on public.users
for each row
execute function public.set_updated_at();
