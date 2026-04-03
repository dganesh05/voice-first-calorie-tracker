-- Pair Supabase Auth accounts with app-level public.users profiles.
-- Run after core tables are created.

-- 1) Backfill any existing auth users that do not have a profile row.
insert into public.users (id, email)
select au.id, au.email
from auth.users au
left join public.users u on u.id = au.id
where u.id is null;

-- 2) Ensure users.id is linked to auth.users.id and cascades on auth user deletion.
do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'users_id_auth_users_fkey'
    ) then
        alter table public.users
            add constraint users_id_auth_users_fkey
            foreign key (id)
            references auth.users(id)
            on delete cascade;
    end if;
end
$$;

-- 3) Auto-create profile row whenever a new auth user is created.
create or replace function public.handle_auth_user_created()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.users (id, email)
    values (new.id, new.email)
    on conflict (id) do update
        set email = excluded.email,
            updated_at = now();

    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
after insert on auth.users
for each row
execute function public.handle_auth_user_created();
