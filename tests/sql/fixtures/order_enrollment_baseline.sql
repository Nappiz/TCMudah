do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'anon') then
        create role anon;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'authenticated') then
        create role authenticated;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'service_role') then
        create role service_role;
    end if;
end;
$$;
create schema storage;
create type public.order_status as enum ('pending', 'approved', 'rejected', 'expired');

create table public.users (
    id uuid primary key,
    role text not null,
    full_name text,
    email text
);
create table public.classes (
    id uuid primary key,
    title text not null,
    price bigint not null,
    visible boolean not null default true,
    batch_id uuid,
    created_at timestamptz not null default now()
);
create table public.packages (
    id uuid primary key,
    title text not null,
    price bigint not null,
    class_ids uuid[] not null default '{}',
    visible boolean not null default true,
    batch_id uuid,
    created_at timestamptz not null default now()
);
create table public.batches (
    id uuid primary key,
    is_active boolean not null default false,
    created_at timestamptz not null default now()
);
create table public.class_offers (
    id uuid primary key,
    class_id uuid not null references public.classes(id) on delete cascade,
    meeting_count integer not null,
    list_price bigint not null,
    price bigint not null,
    visible boolean not null default true
);
create table public.package_items (
    package_id uuid not null references public.packages(id) on delete cascade,
    class_id uuid not null references public.classes(id) on delete restrict,
    class_offer_id uuid not null references public.class_offers(id) on delete restrict,
    created_at timestamptz not null default now(),
    primary key (package_id, class_id)
);
create table public.orders (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id),
    items jsonb not null,
    total bigint not null,
    status public.order_status not null default 'pending',
    proof_url text,
    sender_name text,
    note text,
    created_at timestamptz not null default now()
);
create table public.order_items (
    id bigint generated always as identity primary key,
    order_id uuid not null references public.orders(id) on delete cascade,
    item_id uuid not null,
    item_type text not null,
    item_title text not null,
    qty integer not null,
    unit_price bigint not null,
    line_total bigint not null,
    offer_id uuid,
    meeting_count integer,
    list_price bigint,
    offer_snapshot jsonb
);
create table public.enrollments (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id),
    class_id uuid not null references public.classes(id),
    active boolean not null default true,
    assigned_by uuid,
    created_at timestamptz not null default now(),
    unique (user_id, class_id)
);
create table public.payment_upload_intents (
    path text primary key,
    user_id uuid not null references public.users(id),
    bucket_id text not null,
    content_type text not null,
    max_size_bytes bigint not null,
    expires_at timestamptz not null,
    consumed_at timestamptz
);
create table storage.objects (
    bucket_id text not null,
    name text not null,
    metadata jsonb,
    primary key (bucket_id, name)
);

create function public.admin_update_order_status(p_order_id uuid, p_status text)
returns jsonb language plpgsql as $$
declare result jsonb;
begin
    update public.orders set status = p_status::public.order_status
    where id = p_order_id returning to_jsonb(orders) into result;
    return result;
end;
$$;

create function public.admin_enrollment_candidates(
    p_search text, p_limit integer, p_after_name text, p_after_id uuid
)
returns jsonb language sql stable as $$
select jsonb_build_object(
    'participants', coalesce(jsonb_agg(jsonb_build_object('id', u.id)), '[]'::jsonb)
)
from public.users u
where u.role = 'peserta'
  and exists (
      select 1 from public.orders o
      where o.user_id = u.id and o.status = 'approved'
  );
$$;

-- Previous bootstrap behavior: only approved orders keep a selected participant.
create function public.admin_enrollment_bootstrap(
    p_user_id uuid, p_search text, p_limit integer,
    p_after_name text, p_after_id uuid
)
returns jsonb language plpgsql stable as $$
declare selected_id uuid;
begin
    if p_user_id is not null and exists (
        select 1 from public.users u where u.id = p_user_id and u.role = 'peserta'
          and exists (select 1 from public.orders o where o.user_id = u.id and o.status = 'approved')
    ) then
        selected_id := p_user_id;
    end if;
    return jsonb_build_object('selected_user',
        (select jsonb_build_object('id', u.id) from public.users u where u.id = selected_id));
end;
$$;

insert into public.users (id, role, full_name, email) values
('00000000-0000-0000-0000-000000000001', 'peserta', 'Peserta Lama', 'lama@example.test');
insert into public.classes (id, title, price) values
('10000000-0000-0000-0000-000000000001', 'Matematika', 100000),
('10000000-0000-0000-0000-000000000002', 'Fisika', 120000),
('10000000-0000-0000-0000-000000000003', 'Kimia', 90000);
insert into public.class_offers (id, class_id, meeting_count, list_price, price) values
('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 6, 120000, 100000),
('20000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000002', 4, 140000, 120000),
('20000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000003', 6, 100000, 90000);
insert into public.packages (id, title, price, class_ids) values
('30000000-0000-0000-0000-000000000001', 'Paket Sains', 180000,
 array['10000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000002']::uuid[]);
insert into public.package_items (package_id, class_id, class_offer_id) values
('30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001'),
('30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002');
insert into public.orders (id, user_id, items, total, status) values
('40000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001',
 '[{"item_id":"30000000-0000-0000-0000-000000000001","item_type":"package","item_title":"Paket Sains","qty":1,"price":180000}]',
 180000, 'pending');
insert into public.order_items (order_id, item_id, item_type, item_title, qty, unit_price, line_total)
values ('40000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
        'package', 'Paket Sains', 1, 180000, 180000);
insert into public.enrollments (user_id, class_id, active)
values ('00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', true);
