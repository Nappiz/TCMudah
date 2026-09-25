begin;

set local lock_timeout = '10s';
set local statement_timeout = '10min';

alter table public.classes
    add column if not exists base_price_per_meeting bigint not null default 0
    check (base_price_per_meeting >= 0);

create table if not exists public.class_offers (
    id uuid primary key default gen_random_uuid(),
    class_id uuid not null references public.classes(id) on delete cascade,
    meeting_count integer not null check (meeting_count > 0 and meeting_count <= 100),
    list_price bigint not null check (list_price >= 0),
    price bigint not null check (price >= 0 and price <= list_price),
    is_recommended boolean not null default false,
    visible boolean not null default true,
    sort_order integer not null default 0 check (sort_order >= 0),
    created_at timestamptz not null default now(),
    unique (class_id, meeting_count)
);

create unique index if not exists uq_class_offers_one_recommended
    on public.class_offers (class_id) where is_recommended = true;
alter table public.class_offers
    add constraint class_offers_id_class_id_key unique (id, class_id);
create index if not exists idx_class_offers_class_sort
    on public.class_offers (class_id, visible, sort_order, meeting_count);

-- Every existing class was previously sold as a six-meeting product. Its
-- current price becomes a no-discount legacy offer until an admin supplies
-- the real base/list price.
insert into public.class_offers (
    class_id, meeting_count, list_price, price, is_recommended, visible, sort_order
)
select c.id, 6, c.price, c.price, true, c.visible, 0
from public.classes c
where not exists (
    select 1 from public.class_offers co where co.class_id = c.id
);

create table if not exists public.package_items (
    package_id uuid not null references public.packages(id) on delete cascade,
    class_id uuid not null references public.classes(id) on delete restrict,
    class_offer_id uuid not null,
    created_at timestamptz not null default now(),
    primary key (package_id, class_id),
    unique (package_id, class_offer_id)
);

alter table public.package_items
    add constraint package_items_offer_matches_class_fkey
    foreign key (class_offer_id, class_id)
    references public.class_offers(id, class_id) on delete restrict;

create index if not exists idx_package_items_offer
    on public.package_items (class_offer_id);

insert into public.package_items (package_id, class_id, class_offer_id)
select p.id, selected.class_id, selected.offer_id
from public.packages p
cross join lateral jsonb_array_elements_text(
    coalesce(to_jsonb(p.class_ids), '[]'::jsonb)
) class_ref(class_id)
cross join lateral (
    select co.class_id, co.id as offer_id
    from public.class_offers co
    where co.class_id = class_ref.class_id::uuid
    order by co.is_recommended desc, co.sort_order, co.meeting_count
    limit 1
) selected
on conflict (package_id, class_id) do nothing;

alter table public.order_items add column if not exists offer_id uuid;
alter table public.order_items add column if not exists meeting_count integer;
alter table public.order_items add column if not exists list_price bigint;
alter table public.order_items add column if not exists offer_snapshot jsonb;

alter table public.order_items drop constraint if exists order_items_offer_id_fkey;
alter table public.order_items
    add constraint order_items_offer_id_fkey
    foreign key (offer_id) references public.class_offers(id) on delete set null;

create index if not exists idx_order_items_offer_id
    on public.order_items (offer_id) where offer_id is not null;

create or replace function public.get_public_catalog()
returns jsonb
language sql
stable
set search_path = public
as $$
with active_batch as (
    select id from public.batches where is_active = true
    order by created_at desc limit 1
)
select jsonb_build_object(
    'active_batch_id', (select id from active_batch),
    'mentors', coalesce((
        select jsonb_agg(jsonb_build_object(
            'id', m.id, 'name', m.name, 'angkatan', m.angkatan,
            'achievements', m.achievements, 'visible', m.visible,
            'created_at', m.created_at
        ) order by m.created_at desc, m.id)
        from public.mentors m where m.visible = true
    ), '[]'::jsonb),
    'curriculum', coalesce((
        select jsonb_agg(jsonb_build_object(
            'id', c.id, 'code', c.code, 'name', c.name, 'sem', c.sem,
            'blurb', c.blurb, 'created_at', c.created_at
        ) order by c.sem, c.code, c.id)
        from public.curriculum c
    ), '[]'::jsonb),
    'classes', coalesce((
        select jsonb_agg(jsonb_build_object(
            'id', c.id, 'title', c.title, 'description', c.description,
            'mentor_ids', c.mentor_ids, 'curriculum_ids', c.curriculum_ids,
            'price', c.price, 'base_price_per_meeting', c.base_price_per_meeting,
            'offers', coalesce((
                select jsonb_agg(jsonb_build_object(
                    'id', co.id, 'class_id', co.class_id,
                    'meeting_count', co.meeting_count, 'list_price', co.list_price,
                    'price', co.price, 'is_recommended', co.is_recommended,
                    'visible', co.visible, 'sort_order', co.sort_order,
                    'created_at', co.created_at
                ) order by co.sort_order, co.meeting_count, co.id)
                from public.class_offers co
                where co.class_id = c.id and co.visible = true
            ), '[]'::jsonb),
            'visible', c.visible, 'batch_id', c.batch_id, 'created_at', c.created_at
        ) order by c.created_at desc, c.id)
        from public.classes c
        where c.visible = true
          and (not exists (select 1 from active_batch)
               or c.batch_id = (select id from active_batch))
    ), '[]'::jsonb),
    'packages', coalesce((
        select jsonb_agg(jsonb_build_object(
            'id', p.id, 'title', p.title, 'description', p.description,
            'class_ids', p.class_ids,
            'items', coalesce((
                select jsonb_agg(jsonb_build_object(
                    'class_id', pi.class_id, 'class_offer_id', pi.class_offer_id
                ) order by pi.created_at, pi.class_id)
                from public.package_items pi where pi.package_id = p.id
            ), '[]'::jsonb),
            'price', p.price, 'visible', p.visible,
            'batch_id', p.batch_id, 'created_at', p.created_at
        ) order by p.created_at desc, p.id)
        from public.packages p
        where p.visible = true
          and (not exists (select 1 from active_batch)
               or p.batch_id = (select id from active_batch))
    ), '[]'::jsonb)
);
$$;

create or replace function public.create_order_transactional(
    p_user_id uuid,
    p_items jsonb,
    p_proof_path text,
    p_proof_bucket text,
    p_sender_name text,
    p_note text
)
returns jsonb
language plpgsql
set search_path = public, storage
as $$
declare
    source_item jsonb;
    requested_id uuid;
    requested_offer_id uuid;
    selected_offer_id uuid;
    requested_type text;
    requested_qty integer;
    catalog_title text;
    catalog_price bigint;
    catalog_list_price bigint;
    catalog_meeting_count integer;
    selected_snapshot jsonb;
    enriched_items jsonb := '[]'::jsonb;
    order_total bigint := 0;
    created_order public.orders%rowtype;
    upload_intent public.payment_upload_intents%rowtype;
    uploaded_size bigint;
    uploaded_type text;
begin
    select * into created_order from public.orders
    where user_id = p_user_id and proof_url = p_proof_path;
    if found then
        return jsonb_build_object(
            'id', created_order.id, 'user_id', created_order.user_id,
            'items', created_order.items, 'total', created_order.total,
            'status', created_order.status, 'proof_url', created_order.proof_url,
            'sender_name', created_order.sender_name, 'note', created_order.note,
            'created_at', created_order.created_at
        );
    end if;

    select * into upload_intent from public.payment_upload_intents
    where path = p_proof_path and user_id = p_user_id and bucket_id = p_proof_bucket
    for update;
    if not found then
        raise exception using errcode = 'P0001', message = 'Bukti pembayaran tidak valid atau kedaluwarsa';
    end if;
    if upload_intent.consumed_at is not null then
        select * into created_order from public.orders
        where user_id = p_user_id and proof_url = p_proof_path;
        if found then
            return jsonb_build_object(
                'id', created_order.id, 'user_id', created_order.user_id,
                'items', created_order.items, 'total', created_order.total,
                'status', created_order.status, 'proof_url', created_order.proof_url,
                'sender_name', created_order.sender_name, 'note', created_order.note,
                'created_at', created_order.created_at
            );
        end if;
        raise exception using errcode = 'P0001', message = 'Upload intent sudah dikonsumsi tanpa order';
    end if;
    if upload_intent.expires_at <= now() then
        raise exception using errcode = 'P0001', message = 'Bukti pembayaran tidak valid atau kedaluwarsa';
    end if;

    select nullif(metadata ->> 'size', '')::bigint, metadata ->> 'mimetype'
    into uploaded_size, uploaded_type from storage.objects
    where bucket_id = p_proof_bucket and name = p_proof_path;
    if not found or uploaded_size is null then
        raise exception using errcode = 'P0001', message = 'Bukti pembayaran belum diunggah';
    end if;
    if uploaded_size > upload_intent.max_size_bytes
       or uploaded_type is distinct from upload_intent.content_type then
        raise exception using errcode = 'P0001', message = 'Bukti pembayaran tidak sesuai intent';
    end if;

    if jsonb_typeof(p_items) <> 'array' or jsonb_array_length(p_items) = 0 then
        raise exception using errcode = 'P0001', message = 'Keranjang kosong';
    end if;
    if exists (
        select 1 from jsonb_array_elements(p_items) item
        group by item ->> 'item_type', item ->> 'item_id' having count(*) > 1
    ) then
        raise exception using errcode = 'P0001', message = 'Item order duplikat';
    end if;
    for source_item in select value from jsonb_array_elements(p_items)
    loop
        begin
            requested_id := (source_item ->> 'item_id')::uuid;
            requested_qty := (source_item ->> 'qty')::integer;
            requested_offer_id := nullif(source_item ->> 'offer_id', '')::uuid;
        exception when others then
            raise exception using errcode = 'P0001', message = 'Format item order tidak valid';
        end;
        requested_type := coalesce(source_item ->> 'item_type', 'class');
        if requested_id is null or requested_qty is null
           or requested_type not in ('class', 'package')
           or requested_qty not between 1 and 99 then
            raise exception using errcode = 'P0001', message = 'Item order tidak valid';
        end if;

        selected_offer_id := null;
        catalog_list_price := null;
        catalog_meeting_count := null;
        selected_snapshot := null;

        if requested_type = 'class' and requested_offer_id is not null then
            select c.title, co.price, co.list_price, co.meeting_count, co.id
            into catalog_title, catalog_price, catalog_list_price,
                 catalog_meeting_count, selected_offer_id
            from public.class_offers co
            join public.classes c on c.id = co.class_id
            where c.id = requested_id and c.visible = true
              and co.id = requested_offer_id and co.visible = true;
        elsif requested_type = 'class' then
            select c.title, c.price::bigint, c.price::bigint
            into catalog_title, catalog_price, catalog_list_price
            from public.classes c where c.id = requested_id and c.visible = true;
        else
            select p.title, p.price::bigint, p.price::bigint,
                   jsonb_build_object('items', coalesce((
                       select jsonb_agg(jsonb_build_object(
                           'class_id', pi.class_id,
                           'class_offer_id', pi.class_offer_id,
                           'meeting_count', co.meeting_count,
                           'list_price', co.list_price,
                           'price', co.price
                       ) order by pi.created_at, pi.class_id)
                       from public.package_items pi
                       join public.class_offers co on co.id = pi.class_offer_id
                       where pi.package_id = p.id
                   ), '[]'::jsonb))
            into catalog_title, catalog_price, catalog_list_price, selected_snapshot
            from public.packages p where p.id = requested_id and p.visible = true;
        end if;
        if not found then
            raise exception using errcode = 'P0001', message = 'Item tidak tersedia';
        end if;

        enriched_items := enriched_items || jsonb_build_array(jsonb_build_object(
            'item_id', requested_id, 'item_type', requested_type,
            'item_title', catalog_title, 'qty', requested_qty,
            'price', catalog_price, 'list_price', catalog_list_price,
            'offer_id', selected_offer_id, 'meeting_count', catalog_meeting_count,
            'offer_snapshot', selected_snapshot
        ));
        order_total := order_total + catalog_price * requested_qty;
    end loop;

    if exists (
        select 1
        from jsonb_array_elements(enriched_items) direct_item
        join jsonb_array_elements(enriched_items) package_item
          on direct_item ->> 'item_type' = 'class'
         and package_item ->> 'item_type' = 'package'
        join public.package_items pi
          on pi.package_id = (package_item ->> 'item_id')::uuid
         and pi.class_id = (direct_item ->> 'item_id')::uuid
    ) then
        raise exception using errcode = 'P0001', message = 'Kelas duplikat dengan isi bundle';
    end if;

    insert into public.orders (user_id, items, total, status, proof_url, sender_name, note)
    values (p_user_id, enriched_items, order_total, 'pending', p_proof_path, p_sender_name, p_note)
    returning * into created_order;

    insert into public.order_items (
        order_id, item_id, item_type, item_title, qty, unit_price, line_total,
        offer_id, meeting_count, list_price, offer_snapshot
    )
    select created_order.id, (item ->> 'item_id')::uuid, item ->> 'item_type',
           item ->> 'item_title', (item ->> 'qty')::integer,
           (item ->> 'price')::bigint,
           (item ->> 'qty')::integer * (item ->> 'price')::bigint,
           nullif(item ->> 'offer_id', '')::uuid,
           nullif(item ->> 'meeting_count', '')::integer,
           nullif(item ->> 'list_price', '')::bigint,
           item -> 'offer_snapshot'
    from jsonb_array_elements(enriched_items) item;

    update public.payment_upload_intents set consumed_at = now() where path = p_proof_path;
    return jsonb_build_object(
        'id', created_order.id, 'user_id', created_order.user_id,
        'items', enriched_items, 'total', created_order.total,
        'status', created_order.status, 'proof_url', created_order.proof_url,
        'sender_name', created_order.sender_name, 'note', created_order.note,
        'created_at', created_order.created_at
    );
end;
$$;

-- Order readers expose the immutable offer snapshot as part of every item.
create or replace function public.admin_paginated_orders(
    p_limit integer, p_offset integer, p_search text, p_status text
)
returns jsonb
language sql
stable
set search_path = public, extensions
as $$
with filtered as materialized (
    select o.id, o.user_id, o.total, o.status, o.proof_url, o.sender_name,
           o.note, o.created_at, u.full_name as user_name, u.email as user_email
    from public.orders o left join public.users u on u.id = o.user_id
    where (p_status is null or p_status = '' or o.status::text = p_status)
      and (p_search is null or p_search = ''
        or lower(coalesce(u.full_name, '')) like '%' || lower(p_search) || '%'
        or lower(coalesce(u.email::text, '')) like '%' || lower(p_search) || '%'
        or lower(coalesce(o.sender_name, '')) like '%' || lower(p_search) || '%')
), page as (
    select * from filtered order by created_at desc, id
    limit least(greatest(p_limit, 1), 100) offset greatest(p_offset, 0)
)
select jsonb_build_object(
    'total', (select count(*) from filtered),
    'data', coalesce((select jsonb_agg(jsonb_build_object(
        'id', p.id, 'user_id', p.user_id,
        'items', coalesce((select jsonb_agg(jsonb_build_object(
            'item_id', oi.item_id, 'item_type', oi.item_type,
            'item_title', oi.item_title, 'qty', oi.qty, 'price', oi.unit_price,
            'list_price', oi.list_price, 'offer_id', oi.offer_id,
            'meeting_count', oi.meeting_count, 'offer_snapshot', oi.offer_snapshot
        ) order by oi.id) from public.order_items oi where oi.order_id = p.id), '[]'::jsonb),
        'total', p.total, 'status', p.status, 'proof_url', p.proof_url,
        'sender_name', p.sender_name, 'note', p.note, 'created_at', p.created_at,
        'user_name', p.user_name, 'user_email', p.user_email
    ) order by p.created_at desc, p.id) from page p), '[]'::jsonb)
);
$$;

create or replace function public.admin_update_order_status(p_order_id uuid, p_status text)
returns jsonb
language plpgsql
set search_path = public
as $$
declare result jsonb;
begin
    if p_status not in ('approved', 'rejected', 'expired') then
        raise exception using errcode = 'P0001', message = 'Status order tidak valid';
    end if;
    with updated as (
        update public.orders set status = p_status where id = p_order_id returning *
    )
    select jsonb_build_object(
        'id', o.id, 'user_id', o.user_id,
        'items', coalesce((select jsonb_agg(jsonb_build_object(
            'item_id', oi.item_id, 'item_type', oi.item_type,
            'item_title', oi.item_title, 'qty', oi.qty, 'price', oi.unit_price,
            'list_price', oi.list_price, 'offer_id', oi.offer_id,
            'meeting_count', oi.meeting_count, 'offer_snapshot', oi.offer_snapshot
        ) order by oi.id) from public.order_items oi where oi.order_id = o.id), '[]'::jsonb),
        'total', o.total, 'status', o.status, 'proof_url', o.proof_url,
        'sender_name', o.sender_name, 'note', o.note, 'created_at', o.created_at,
        'user_name', u.full_name, 'user_email', u.email
    ) into result from updated o left join public.users u on u.id = o.user_id;
    return result;
end;
$$;

revoke all on table public.class_offers from public, anon, authenticated;
revoke all on table public.package_items from public, anon, authenticated;
grant all on table public.class_offers to service_role;
grant all on table public.package_items to service_role;

revoke all on function public.get_public_catalog() from public, anon, authenticated;
revoke all on function public.create_order_transactional(uuid, jsonb, text, text, text, text) from public, anon, authenticated;
revoke all on function public.admin_paginated_orders(integer, integer, text, text) from public, anon, authenticated;
revoke all on function public.admin_update_order_status(uuid, text) from public, anon, authenticated;
grant execute on function public.get_public_catalog() to service_role;
grant execute on function public.create_order_transactional(uuid, jsonb, text, text, text, text) to service_role;
grant execute on function public.admin_paginated_orders(integer, integer, text, text) to service_role;
grant execute on function public.admin_update_order_status(uuid, text) to service_role;

commit;
