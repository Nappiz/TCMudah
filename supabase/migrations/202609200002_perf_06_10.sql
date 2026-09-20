begin;

set local lock_timeout = '10s';
set local statement_timeout = '10min';
create schema if not exists extensions;
create extension if not exists pg_trgm with schema extensions;
set local search_path = public, extensions;

-- Search, pagination, and normalized order analytics indexes.
create index if not exists idx_users_full_name_trgm
    on public.users using gin (lower(full_name) gin_trgm_ops);
create index if not exists idx_users_email_trgm
    on public.users using gin (lower(email::text) gin_trgm_ops);
create index if not exists idx_orders_sender_name_trgm
    on public.orders using gin (lower(sender_name) gin_trgm_ops);
create index if not exists idx_orders_user_created_at
    on public.orders (user_id, created_at desc);
create index if not exists idx_feedbacks_class_created_at
    on public.feedbacks (class_id, created_at desc);
create index if not exists idx_shortlinks_created_at
    on public.shortlinks (created_at desc);
create index if not exists idx_shortlinks_search_trgm
    on public.shortlinks using gin (
        lower(
            slug || ' ' || url || ' ' || coalesce(title, '') || ' ' || coalesce(description, '')
        ) gin_trgm_ops
    );

-- Consolidate legacy duplicate enrollment rows before enforcing idempotent upserts.
with ranked as (
    select
        id,
        row_number() over (
            partition by user_id, class_id
            order by active desc, created_at desc, id desc
        ) as row_number,
        bool_or(active) over (partition by user_id, class_id) as any_active
    from public.enrollments
)
update public.enrollments e
set active = r.any_active
from ranked r
where e.id = r.id
  and r.row_number = 1
  and e.active is distinct from r.any_active;

with ranked as (
    select
        id,
        row_number() over (
            partition by user_id, class_id
            order by active desc, created_at desc, id desc
        ) as row_number
    from public.enrollments
)
delete from public.enrollments e
using ranked r
where e.id = r.id
  and r.row_number > 1;

create unique index if not exists uq_enrollments_user_class
    on public.enrollments (user_id, class_id);


-- Order items are normalized for durable title/price snapshots and fast analytics.
create table if not exists public.order_items (
    id bigint generated always as identity primary key,
    order_id uuid not null references public.orders(id) on delete cascade,
    item_id uuid not null,
    item_type text not null check (item_type in ('class', 'package')),
    item_title text not null,
    qty integer not null check (qty > 0),
    unit_price bigint not null check (unit_price >= 0),
    line_total bigint not null check (line_total >= 0),
    created_at timestamptz not null default now(),
    unique (order_id, item_type, item_id)
);

create index if not exists idx_order_items_order_id
    on public.order_items (order_id);
create index if not exists idx_order_items_type_item
    on public.order_items (item_type, item_id);

-- Abort instead of silently dropping malformed historical data during normalization.
do $$
begin
    if exists (
        select 1
        from public.orders o
        where o.items is not null
          and jsonb_typeof(o.items::jsonb) <> 'array'
    ) then
        raise exception using
            errcode = 'P0001',
            message = 'Order item backfill dibatalkan: orders.items harus berupa array';
    end if;

    if exists (
        select 1
        from public.orders o
        cross join lateral jsonb_array_elements(coalesce(o.items::jsonb, '[]'::jsonb)) item
        where coalesce(item ->> 'item_id', item ->> 'class_id') is null
           or coalesce(item ->> 'item_id', item ->> 'class_id')
                !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
           or coalesce(item ->> 'item_type', 'class') not in ('class', 'package')
           or (item ->> 'qty' is not null and item ->> 'qty' !~ '^[0-9]{1,9}$')
           or item ->> 'price' is null
           or item ->> 'price' !~ '^[0-9]{1,18}$'
    ) then
        raise exception using
            errcode = 'P0001',
            message = 'Order item backfill dibatalkan: terdapat item legacy yang tidak valid';
    end if;
end;
$$;

with parsed_order_items as (
    select
        o.id as order_id,
        coalesce(item.value ->> 'item_id', item.value ->> 'class_id')::uuid as item_id,
        coalesce(item.value ->> 'item_type', 'class') as item_type,
        coalesce(
            nullif(item.value ->> 'item_title', ''),
            case
                when coalesce(item.value ->> 'item_type', 'class') = 'package'
                    then p.title
                else c.title
            end,
            'Unknown Item'
        ) as item_title,
        least(99, greatest(
            case
                when item.value ->> 'qty' ~ '^[0-9]{1,9}$'
                    then (item.value ->> 'qty')::integer
                else 1
            end,
            1
        )) as qty,
        greatest(
            case
                when item.value ->> 'price' ~ '^-?[0-9]{1,18}$'
                    then (item.value ->> 'price')::bigint
                else 0
            end,
            0
        ) as unit_price,
        o.created_at,
        item.position
    from public.orders o
    cross join lateral jsonb_array_elements(coalesce(o.items::jsonb, '[]'::jsonb))
        with ordinality as item(value, position)
    left join public.classes c
        on c.id::text = coalesce(item.value ->> 'item_id', item.value ->> 'class_id')
       and coalesce(item.value ->> 'item_type', 'class') = 'class'
    left join public.packages p
        on p.id::text = coalesce(item.value ->> 'item_id', item.value ->> 'class_id')
       and item.value ->> 'item_type' = 'package'
    where coalesce(item.value ->> 'item_id', item.value ->> 'class_id')
              ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
      and coalesce(item.value ->> 'item_type', 'class') in ('class', 'package')
),
deduplicated_order_items as (
    select
        order_id,
        item_id,
        item_type,
        (array_agg(item_title order by position desc))[1] as item_title,
        sum(qty)::integer as qty,
        (array_agg(unit_price order by position desc))[1] as unit_price,
        sum(qty * unit_price)::bigint as line_total,
        max(created_at) as created_at
    from parsed_order_items
    group by order_id, item_type, item_id
)
insert into public.order_items (
    order_id,
    item_id,
    item_type,
    item_title,
    qty,
    unit_price,
    line_total,
    created_at
)
select order_id, item_id, item_type, item_title, qty, unit_price, line_total, created_at
from deduplicated_order_items
on conflict (order_id, item_type, item_id) do nothing;


-- PERF-02/03 search variants use the trigram expression indexes above.
create or replace function public.admin_paginated_users(
    p_limit integer,
    p_offset integer,
    p_search text,
    p_role text
)
returns jsonb
language sql
stable
set search_path = public, extensions
as $$
with filtered as materialized (
    select
        u.id,
        u.email,
        u.full_name,
        u.nim,
        u.role,
        u.created_at,
        case u.role::text
            when 'superadmin' then 0
            when 'admin' then 1
            when 'mentor' then 2
            else 3
        end as role_rank
    from public.users u
    where (p_role is null or p_role = '' or u.role::text = p_role)
      and (
          p_search is null
          or p_search = ''
          or lower(u.full_name) like '%' || lower(p_search) || '%'
          or lower(u.email::text) like '%' || lower(p_search) || '%'
      )
), page as (
    select *
    from filtered
    order by role_rank, created_at desc, id
    limit least(greatest(p_limit, 1), 100)
    offset greatest(p_offset, 0)
)
select jsonb_build_object(
    'total', (select count(*) from filtered),
    'data', coalesce((
        select jsonb_agg(
            jsonb_build_object(
                'id', id,
                'email', email,
                'full_name', full_name,
                'nim', nim,
                'role', role,
                'created_at', created_at
            )
            order by role_rank, created_at desc, id
        )
        from page
    ), '[]'::jsonb)
);
$$;

create or replace function public.admin_enrollment_candidates(
    p_search text,
    p_limit integer,
    p_after_name text,
    p_after_id uuid
)
returns jsonb
language sql
stable
set search_path = public, extensions
as $$
with eligible as materialized (
    select
        u.id,
        u.full_name,
        u.email,
        lower(coalesce(u.full_name, '')) as sort_name
    from public.users u
    where u.role = 'peserta'
      and exists (
          select 1
          from public.orders o
          where o.user_id = u.id
            and o.status = 'approved'
      )
      and (
          p_search is null
          or p_search = ''
          or lower(u.full_name) like '%' || lower(p_search) || '%'
          or lower(u.email::text) like '%' || lower(p_search) || '%'
      )
      and (
          p_after_name is null
          or p_after_id is null
          or (lower(coalesce(u.full_name, '')), u.id) > (p_after_name, p_after_id)
      )
), page_plus_one as (
    select *
    from eligible
    order by sort_name, id
    limit least(greatest(p_limit, 1), 100) + 1
), page as (
    select *
    from page_plus_one
    order by sort_name, id
    limit least(greatest(p_limit, 1), 100)
)
select jsonb_build_object(
    'participants', coalesce((
        select jsonb_agg(
            jsonb_build_object('id', id, 'full_name', full_name, 'email', email)
            order by sort_name, id
        )
        from page
    ), '[]'::jsonb),
    'has_more', (select count(*) > least(greatest(p_limit, 1), 100) from page_plus_one),
    'next_after_name', case
        when (select count(*) > least(greatest(p_limit, 1), 100) from page_plus_one)
        then (select sort_name from page order by sort_name desc, id desc limit 1)
        else null
    end,
    'next_after_id', case
        when (select count(*) > least(greatest(p_limit, 1), 100) from page_plus_one)
        then (select id from page order by sort_name desc, id desc limit 1)
        else null
    end
);
$$;


create or replace function public.admin_set_user_enrollments(
    p_user_id uuid,
    p_class_ids uuid[],
    p_assigned_by uuid
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
    desired_ids uuid[] := coalesce(p_class_ids, '{}'::uuid[]);
    missing_class_id uuid;
begin
    if not exists (
        select 1 from public.users where id = p_user_id and role = 'peserta'
    ) then
        raise exception using errcode = 'P0001', message = 'Peserta tidak ditemukan';
    end if;

    select requested.class_id
    into missing_class_id
    from unnest(desired_ids) requested(class_id)
    left join public.classes c on c.id = requested.class_id
    where c.id is null
    limit 1;

    if missing_class_id is not null then
        raise exception using errcode = 'P0001', message = 'Kelas tidak ditemukan';
    end if;

    delete from public.enrollments
    where user_id = p_user_id
      and not (class_id = any(desired_ids));

    insert into public.enrollments (user_id, class_id, active, assigned_by)
    select p_user_id, requested.class_id, true, p_assigned_by
    from (select distinct unnest(desired_ids) as class_id) requested
    on conflict (user_id, class_id) do update
    set active = true,
        assigned_by = excluded.assigned_by;

    return coalesce((
        select jsonb_agg(
            jsonb_build_object(
                'id', e.id,
                'user_id', e.user_id,
                'class_id', e.class_id,
                'active', e.active,
                'assigned_by', e.assigned_by,
                'created_at', e.created_at
            )
            order by e.created_at desc, e.id
        )
        from public.enrollments e
        where e.user_id = p_user_id
    ), '[]'::jsonb);
end;
$$;

create or replace function public.admin_set_package_enrollments(
    p_user_id uuid,
    p_package_id uuid,
    p_assigned_by uuid
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
    package_class_ids uuid[];
    missing_class_id uuid;
begin
    if not exists (
        select 1 from public.users where id = p_user_id and role = 'peserta'
    ) then
        raise exception using errcode = 'P0001', message = 'Peserta tidak ditemukan';
    end if;

    select coalesce(
        array(
            select jsonb_array_elements_text(coalesce(to_jsonb(p.class_ids), '[]'::jsonb))::uuid
        ),
        '{}'::uuid[]
    )
    into package_class_ids
    from public.packages p
    where p.id = p_package_id;

    if not found then
        raise exception using errcode = 'P0001', message = 'Paket tidak ditemukan';
    end if;
    if cardinality(package_class_ids) = 0 then
        raise exception using errcode = 'P0001', message = 'Paket ini kosong';
    end if;

    select requested.class_id
    into missing_class_id
    from unnest(package_class_ids) requested(class_id)
    left join public.classes c on c.id = requested.class_id
    where c.id is null
    limit 1;

    if missing_class_id is not null then
        raise exception using errcode = 'P0001', message = 'Kelas paket tidak ditemukan';
    end if;

    insert into public.enrollments (user_id, class_id, active, assigned_by)
    select p_user_id, requested.class_id, true, p_assigned_by
    from (select distinct unnest(package_class_ids) as class_id) requested
    join public.classes c on c.id = requested.class_id
    on conflict (user_id, class_id) do update
    set active = true,
        assigned_by = excluded.assigned_by;

    return coalesce((
        select jsonb_agg(
            jsonb_build_object(
                'id', e.id,
                'user_id', e.user_id,
                'class_id', e.class_id,
                'active', e.active,
                'assigned_by', e.assigned_by,
                'created_at', e.created_at
            )
            order by e.created_at desc, e.id
        )
        from public.enrollments e
        where e.user_id = p_user_id
    ), '[]'::jsonb);
end;
$$;


create or replace function public.admin_paginated_orders(
    p_limit integer,
    p_offset integer,
    p_search text,
    p_status text
)
returns jsonb
language sql
stable
set search_path = public, extensions
as $$
with filtered as materialized (
    select
        o.id,
        o.user_id,
        o.total,
        o.status,
        o.proof_url,
        o.sender_name,
        o.note,
        o.created_at,
        u.full_name as user_name,
        u.email as user_email
    from public.orders o
    left join public.users u on u.id = o.user_id
    where (p_status is null or p_status = '' or o.status::text = p_status)
      and (
          p_search is null
          or p_search = ''
          or lower(coalesce(u.full_name, '')) like '%' || lower(p_search) || '%'
          or lower(coalesce(u.email::text, '')) like '%' || lower(p_search) || '%'
          or lower(coalesce(o.sender_name, '')) like '%' || lower(p_search) || '%'
      )
), page as (
    select *
    from filtered
    order by created_at desc, id
    limit least(greatest(p_limit, 1), 100)
    offset greatest(p_offset, 0)
)
select jsonb_build_object(
    'total', (select count(*) from filtered),
    'data', coalesce((
        select jsonb_agg(
            jsonb_build_object(
                'id', p.id,
                'user_id', p.user_id,
                'items', coalesce((
                    select jsonb_agg(
                        jsonb_build_object(
                            'item_id', oi.item_id,
                            'item_type', oi.item_type,
                            'item_title', oi.item_title,
                            'qty', oi.qty,
                            'price', oi.unit_price
                        )
                        order by oi.id
                    )
                    from public.order_items oi
                    where oi.order_id = p.id
                ), '[]'::jsonb),
                'total', p.total,
                'status', p.status,
                'proof_url', p.proof_url,
                'sender_name', p.sender_name,
                'note', p.note,
                'created_at', p.created_at,
                'user_name', p.user_name,
                'user_email', p.user_email
            )
            order by p.created_at desc, p.id
        )
        from page p
    ), '[]'::jsonb)
);
$$;

create or replace function public.create_order_transactional(
    p_user_id uuid,
    p_items jsonb,
    p_proof_url text,
    p_sender_name text,
    p_note text
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
    source_item jsonb;
    requested_id uuid;
    requested_type text;
    requested_qty integer;
    catalog_title text;
    catalog_price bigint;
    enriched_items jsonb := '[]'::jsonb;
    order_total bigint := 0;
    created_order public.orders%rowtype;
begin
    if jsonb_typeof(p_items) <> 'array' or jsonb_array_length(p_items) = 0 then
        raise exception using errcode = 'P0001', message = 'Keranjang kosong';
    end if;

    if exists (
        select 1
        from jsonb_array_elements(p_items) item
        group by item ->> 'item_type', item ->> 'item_id'
        having count(*) > 1
    ) then
        raise exception using errcode = 'P0001', message = 'Item order duplikat';
    end if;

    for source_item in select value from jsonb_array_elements(p_items)
    loop
        begin
            requested_id := (source_item ->> 'item_id')::uuid;
            requested_qty := (source_item ->> 'qty')::integer;
        exception when others then
            raise exception using errcode = 'P0001', message = 'Format item order tidak valid';
        end;

        requested_type := coalesce(source_item ->> 'item_type', 'class');
        if requested_id is null
           or requested_qty is null
           or requested_type not in ('class', 'package')
           or requested_qty not between 1 and 99 then
            raise exception using errcode = 'P0001', message = 'Item order tidak valid';
        end if;

        if requested_type = 'class' then
            select c.title, c.price::bigint
            into catalog_title, catalog_price
            from public.classes c
            where c.id = requested_id and c.visible = true;
        else
            select p.title, p.price::bigint
            into catalog_title, catalog_price
            from public.packages p
            where p.id = requested_id and p.visible = true;
        end if;

        if not found then
            raise exception using errcode = 'P0001', message = 'Item tidak tersedia';
        end if;

        enriched_items := enriched_items || jsonb_build_array(
            jsonb_build_object(
                'item_id', requested_id,
                'item_type', requested_type,
                'item_title', catalog_title,
                'qty', requested_qty,
                'price', catalog_price
            )
        );
        order_total := order_total + catalog_price * requested_qty;
    end loop;

    insert into public.orders (
        user_id, items, total, status, proof_url, sender_name, note
    ) values (
        p_user_id,
        enriched_items,
        order_total,
        'pending',
        p_proof_url,
        p_sender_name,
        p_note
    ) returning * into created_order;

    insert into public.order_items (
        order_id, item_id, item_type, item_title, qty, unit_price, line_total
    )
    select
        created_order.id,
        (item ->> 'item_id')::uuid,
        item ->> 'item_type',
        item ->> 'item_title',
        (item ->> 'qty')::integer,
        (item ->> 'price')::bigint,
        (item ->> 'qty')::integer * (item ->> 'price')::bigint
    from jsonb_array_elements(enriched_items) item;

    return jsonb_build_object(
        'id', created_order.id,
        'user_id', created_order.user_id,
        'items', enriched_items,
        'total', created_order.total,
        'status', created_order.status,
        'proof_url', created_order.proof_url,
        'sender_name', created_order.sender_name,
        'note', created_order.note,
        'created_at', created_order.created_at
    );
end;
$$;

create or replace function public.admin_update_order_status(
    p_order_id uuid,
    p_status text
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
    result jsonb;
begin
    if p_status not in ('approved', 'rejected', 'expired') then
        raise exception using errcode = 'P0001', message = 'Status order tidak valid';
    end if;

    with updated as (
        update public.orders
        set status = p_status
        where id = p_order_id
        returning *
    )
    select jsonb_build_object(
        'id', o.id,
        'user_id', o.user_id,
        'items', coalesce((
            select jsonb_agg(
                jsonb_build_object(
                    'item_id', oi.item_id,
                    'item_type', oi.item_type,
                    'item_title', oi.item_title,
                    'qty', oi.qty,
                    'price', oi.unit_price
                )
                order by oi.id
            )
            from public.order_items oi
            where oi.order_id = o.id
        ), '[]'::jsonb),
        'total', o.total,
        'status', o.status,
        'proof_url', o.proof_url,
        'sender_name', o.sender_name,
        'note', o.note,
        'created_at', o.created_at,
        'user_name', u.full_name,
        'user_email', u.email
    )
    into result
    from updated o
    left join public.users u on u.id = o.user_id;

    return result;
end;
$$;


create or replace function public.admin_paginated_feedbacks(
    p_limit integer,
    p_offset integer,
    p_class_id uuid
)
returns jsonb
language sql
stable
set search_path = public
as $$
with filtered as materialized (
    select
        f.id,
        f.class_id,
        f.text,
        f.rating,
        f.created_at,
        c.title as class_title
    from public.feedbacks f
    left join public.classes c on c.id = f.class_id
    where p_class_id is null or f.class_id = p_class_id
), page as (
    select * from filtered
    order by created_at desc, id
    limit least(greatest(p_limit, 1), 100)
    offset greatest(p_offset, 0)
)
select jsonb_build_object(
    'total', (select count(*) from filtered),
    'data', coalesce((select jsonb_agg(to_jsonb(page) order by created_at desc, id) from page), '[]'::jsonb)
);
$$;

create or replace function public.admin_paginated_shortlinks(
    p_limit integer,
    p_offset integer,
    p_search text
)
returns jsonb
language sql
stable
set search_path = public, extensions
as $$
with filtered as materialized (
    select id, slug, url, title, description, active, clicks, created_by, created_at
    from public.shortlinks
    where p_search is null
       or p_search = ''
       or lower(
            slug || ' ' || url || ' ' || coalesce(title, '') || ' ' || coalesce(description, '')
          ) like '%' || lower(p_search) || '%'
), page as (
    select * from filtered
    order by created_at desc, id
    limit least(greatest(p_limit, 1), 100)
    offset greatest(p_offset, 0)
)
select jsonb_build_object(
    'total', (select count(*) from filtered),
    'data', coalesce((select jsonb_agg(to_jsonb(page) order by created_at desc, id) from page), '[]'::jsonb)
);
$$;


create or replace function public.get_public_catalog()
returns jsonb
language sql
stable
set search_path = public
as $$
with active_batch as (
    select id
    from public.batches
    where is_active = true
    order by created_at desc
    limit 1
)
select jsonb_build_object(
    'active_batch_id', (select id from active_batch),
    'mentors', coalesce((
        select jsonb_agg(
            jsonb_build_object(
                'id', m.id,
                'name', m.name,
                'angkatan', m.angkatan,
                'achievements', m.achievements,
                'visible', m.visible,
                'created_at', m.created_at
            ) order by m.created_at desc, m.id
        )
        from public.mentors m
        where m.visible = true
    ), '[]'::jsonb),
    'curriculum', coalesce((
        select jsonb_agg(
            jsonb_build_object(
                'id', c.id,
                'code', c.code,
                'name', c.name,
                'sem', c.sem,
                'blurb', c.blurb,
                'created_at', c.created_at
            ) order by c.sem, c.code, c.id
        )
        from public.curriculum c
    ), '[]'::jsonb),
    'classes', coalesce((
        select jsonb_agg(
            jsonb_build_object(
                'id', c.id,
                'title', c.title,
                'description', c.description,
                'mentor_ids', c.mentor_ids,
                'curriculum_ids', c.curriculum_ids,
                'price', c.price,
                'visible', c.visible,
                'batch_id', c.batch_id,
                'created_at', c.created_at
            ) order by c.created_at desc, c.id
        )
        from public.classes c
        where c.visible = true
          and (
              not exists (select 1 from active_batch)
              or c.batch_id = (select id from active_batch)
          )
    ), '[]'::jsonb),
    'packages', coalesce((
        select jsonb_agg(
            jsonb_build_object(
                'id', p.id,
                'title', p.title,
                'description', p.description,
                'class_ids', p.class_ids,
                'price', p.price,
                'visible', p.visible,
                'batch_id', p.batch_id,
                'created_at', p.created_at
            ) order by p.created_at desc, p.id
        )
        from public.packages p
        where p.visible = true
          and (
              not exists (select 1 from active_batch)
              or p.batch_id = (select id from active_batch)
          )
    ), '[]'::jsonb)
);
$$;


-- Dashboard item analytics now use normalized order_items instead of expanding JSON.
create or replace function public.admin_dashboard_overview(
    p_start_at timestamptz,
    p_end_at timestamptz,
    p_days integer
)
returns jsonb
language sql
stable
set search_path = public
as $$
with
user_stats as (
    select
        count(*) as total_users,
        count(*) filter (where role = 'superadmin') as superadmin,
        count(*) filter (where role = 'admin') as admin,
        count(*) filter (where role = 'mentor') as mentor,
        count(*) filter (where role = 'peserta') as peserta,
        count(*) filter (where created_at >= now() - interval '30 days') as new_users_30d
    from public.users
),
content_stats as (
    select
        (select count(*) from public.curriculum) as total_curriculum,
        (select count(*) from public.testimonials) as total_testimonials,
        (select count(*) from public.testimonials where visible = true) as visible_testimonials,
        (select count(*) from public.mentors) as total_mentors,
        (select count(*) from public.mentors where visible = true) as visible_mentors,
        (select count(*) from public.classes) as total_classes,
        (select count(*) from public.classes where visible = true) as visible_classes
),
global_order_stats as (
    select
        count(*) as total_orders,
        count(*) filter (where status = 'pending') as pending_orders,
        count(*) filter (where status = 'approved') as approved_orders,
        count(*) filter (where status = 'rejected') as rejected_orders,
        count(*) filter (where status = 'expired') as expired_orders,
        coalesce(sum(total) filter (where status = 'approved'), 0) as revenue_approved,
        coalesce(sum(total) filter (where status = 'approved' and created_at >= now() - interval '30 days'), 0) as revenue_30d,
        count(distinct user_id) filter (where status = 'approved') as participants_active
    from public.orders
),
period_orders as materialized (
    select o.*
    from public.orders o
    where (p_start_at is null or o.created_at >= p_start_at)
      and (p_end_at is null or o.created_at < p_end_at)
),
period_order_stats as (
    select
        count(*) as total_orders,
        count(*) filter (where status = 'pending') as pending_orders,
        count(*) filter (where status = 'approved') as approved_orders,
        count(*) filter (where status = 'rejected') as rejected_orders,
        count(*) filter (where status = 'expired') as expired_orders,
        coalesce(sum(total) filter (where status = 'approved'), 0) as revenue_approved
    from period_orders
),
series_days as (
    select generate_series(
        current_date - (least(greatest(p_days, 1), 90) - 1),
        current_date,
        interval '1 day'
    )::date as day
),
series as (
    select
        d.day,
        count(o.id) as order_count,
        coalesce(sum(o.total) filter (where o.status = 'approved'), 0) as revenue
    from series_days d
    left join public.orders o
      on o.created_at >= d.day::timestamptz
     and o.created_at < (d.day + 1)::timestamptz
    group by d.day
    order by d.day
),
pending_order_rows as (
    select o.id, o.user_id, u.full_name as user_name, u.email as user_email,
           o.sender_name, o.total, o.status, o.created_at
    from public.orders o
    left join public.users u on u.id = o.user_id
    where o.status = 'pending'
    order by o.created_at desc, o.id
    limit 5
),
recent_order_rows as (
    select o.id, o.user_id, u.full_name as user_name, u.email as user_email,
           o.sender_name, o.total, o.status, o.created_at
    from public.orders o
    left join public.users u on u.id = o.user_id
    order by o.created_at desc, o.id
    limit 15
),
period_items as (
    select po.status, oi.item_id, oi.item_type, oi.item_title, oi.qty,
           oi.unit_price, oi.line_total, oi.created_at
    from period_orders po
    join public.order_items oi on oi.order_id = po.id
),
top_class_rows as (
    select
        pi.item_id as id,
        (array_agg(pi.item_title order by pi.created_at desc))[1] as title,
        sum(pi.qty)::bigint as count,
        sum(pi.line_total)::bigint as revenue
    from period_items pi
    where pi.status = 'approved' and pi.item_type = 'class'
    group by pi.item_id
    order by revenue desc, id
    limit 5
),
revenue_split as (
    select
        coalesce(sum(line_total) filter (where status = 'approved' and item_type = 'class'), 0)::bigint as class_revenue,
        coalesce(sum(line_total) filter (where status = 'approved' and item_type = 'package'), 0)::bigint as package_revenue
    from period_items
)
select jsonb_build_object(
    'stats', (
        select jsonb_build_object(
            'total_users', us.total_users, 'superadmin', us.superadmin,
            'admin', us.admin, 'mentor', us.mentor, 'peserta', us.peserta,
            'new_users_30d', us.new_users_30d,
            'total_curriculum', cs.total_curriculum,
            'total_testimonials', cs.total_testimonials,
            'visible_testimonials', cs.visible_testimonials,
            'hidden_testimonials', cs.total_testimonials - cs.visible_testimonials,
            'total_mentors', cs.total_mentors, 'visible_mentors', cs.visible_mentors,
            'total_classes', cs.total_classes, 'visible_classes', cs.visible_classes,
            'class_per_mentor', case when cs.total_mentors = 0 then 0 else cs.total_classes::numeric / cs.total_mentors end,
            'total_orders', gos.total_orders, 'pending_orders', gos.pending_orders,
            'approved_orders', gos.approved_orders, 'rejected_orders', gos.rejected_orders,
            'expired_orders', gos.expired_orders, 'revenue_approved', gos.revenue_approved,
            'revenue_30d', gos.revenue_30d, 'participants_active', gos.participants_active,
            'aov', case when gos.approved_orders = 0 then 0 else gos.revenue_approved::numeric / gos.approved_orders end,
            'approval_rate', case when gos.total_orders = 0 then 0 else round(gos.approved_orders::numeric * 100 / gos.total_orders) end,
            'order_series', coalesce((select jsonb_agg(jsonb_build_object('key', day::text, 'value', order_count) order by day) from series), '[]'::jsonb),
            'revenue_series', coalesce((select jsonb_agg(jsonb_build_object('key', day::text, 'value', revenue) order by day) from series), '[]'::jsonb)
        )
        from user_stats us cross join content_stats cs cross join global_order_stats gos
    ),
    'period', (
        select jsonb_build_object(
            'total_orders', pos.total_orders, 'pending_orders', pos.pending_orders,
            'approved_orders', pos.approved_orders, 'rejected_orders', pos.rejected_orders,
            'expired_orders', pos.expired_orders, 'revenue_approved', pos.revenue_approved,
            'aov', case when pos.approved_orders = 0 then 0 else pos.revenue_approved::numeric / pos.approved_orders end,
            'approval_rate', case when pos.total_orders = 0 then 0 else round(pos.approved_orders::numeric * 100 / pos.total_orders) end,
            'class_revenue', rs.class_revenue, 'package_revenue', rs.package_revenue,
            'top_classes', coalesce((select jsonb_agg(jsonb_build_object('id', id, 'title', title, 'count', count, 'revenue', revenue) order by revenue desc, id) from top_class_rows), '[]'::jsonb)
        )
        from period_order_stats pos cross join revenue_split rs
    ),
    'pending_latest', coalesce((select jsonb_agg(to_jsonb(por) order by por.created_at desc, por.id) from pending_order_rows por), '[]'::jsonb),
    'recent_orders', coalesce((select jsonb_agg(to_jsonb(ror) order by ror.created_at desc, ror.id) from recent_order_rows ror), '[]'::jsonb)
);
$$;


revoke all on table public.order_items from public, anon, authenticated;
grant all on table public.order_items to service_role;
grant usage, select on sequence public.order_items_id_seq to service_role;

revoke all on function public.admin_set_user_enrollments(uuid, uuid[], uuid) from public, anon, authenticated;
revoke all on function public.admin_set_package_enrollments(uuid, uuid, uuid) from public, anon, authenticated;
revoke all on function public.admin_paginated_orders(integer, integer, text, text) from public, anon, authenticated;
revoke all on function public.create_order_transactional(uuid, jsonb, text, text, text) from public, anon, authenticated;
revoke all on function public.admin_update_order_status(uuid, text) from public, anon, authenticated;
revoke all on function public.admin_paginated_feedbacks(integer, integer, uuid) from public, anon, authenticated;
revoke all on function public.admin_paginated_shortlinks(integer, integer, text) from public, anon, authenticated;
revoke all on function public.get_public_catalog() from public, anon, authenticated;

grant execute on function public.admin_set_user_enrollments(uuid, uuid[], uuid) to service_role;
grant execute on function public.admin_set_package_enrollments(uuid, uuid, uuid) to service_role;
grant execute on function public.admin_paginated_orders(integer, integer, text, text) to service_role;
grant execute on function public.create_order_transactional(uuid, jsonb, text, text, text) to service_role;
grant execute on function public.admin_update_order_status(uuid, text) to service_role;
grant execute on function public.admin_paginated_feedbacks(integer, integer, uuid) to service_role;
grant execute on function public.admin_paginated_shortlinks(integer, integer, text) to service_role;
grant execute on function public.get_public_catalog() to service_role;

commit;
