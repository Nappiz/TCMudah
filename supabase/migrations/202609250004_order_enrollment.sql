begin;

set local lock_timeout = '10s';
set local statement_timeout = '10min';

-- Rows already in orders were fulfilled through the manual workflow. The
-- replacement checkout function explicitly opts new orders into automation.
alter table public.orders
    add column fulfillment_mode text not null default 'legacy_manual'
    check (fulfillment_mode in ('legacy_manual', 'automatic'));

alter table public.classes add column archived_at timestamptz;
alter table public.packages add column archived_at timestamptz;
alter table public.classes
    add constraint classes_archived_hidden check (archived_at is null or visible = false);
alter table public.packages
    add constraint packages_archived_hidden check (archived_at is null or visible = false);

-- Multiple purchases of one class remain separate historical grants, while
-- enrollments keeps the participant's effective access as one row per class.
create table public.order_enrollment_grants (
    id bigint generated always as identity primary key,
    order_id uuid not null references public.orders(id) on delete restrict,
    order_item_id bigint not null references public.order_items(id) on delete restrict,
    user_id uuid not null references public.users(id) on delete restrict,
    class_id uuid not null references public.classes(id) on delete restrict,
    package_id uuid,
    class_offer_id uuid,
    class_title text not null check (length(trim(class_title)) > 0),
    meeting_count integer check (meeting_count is null or meeting_count > 0),
    created_at timestamptz not null default now(),
    unique (order_item_id, class_id)
);
create index idx_order_enrollment_grants_user_class
    on public.order_enrollment_grants (user_id, class_id);
create index idx_order_enrollment_grants_package_user
    on public.order_enrollment_grants (package_id, user_id)
    where package_id is not null;

create or replace function public.admin_archive_package(p_package_id uuid)
returns jsonb
language plpgsql
set search_path = public
as $$
declare archived public.packages%rowtype;
begin
    update public.packages
    set visible = false, archived_at = now()
    where id = p_package_id and archived_at is null
    returning * into archived;
    if not found then return null; end if;
    return to_jsonb(archived);
end;
$$;

create or replace function public.admin_archive_class(p_class_id uuid)
returns jsonb
language plpgsql
set search_path = public
as $$
declare archived public.classes%rowtype;
begin
    update public.classes
    set visible = false, archived_at = now()
    where id = p_class_id and archived_at is null
    returning * into archived;
    if not found then return null; end if;

    update public.packages p
    set visible = false, archived_at = now()
    where p.archived_at is null
      and exists (
          select 1 from public.package_items pi
          where pi.package_id = p.id and pi.class_id = p_class_id
      );
    return to_jsonb(archived);
end;
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
            'status', created_order.status,
            'fulfillment_mode', created_order.fulfillment_mode,
            'proof_url', created_order.proof_url,
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
                'status', created_order.status,
                'fulfillment_mode', created_order.fulfillment_mode,
                'proof_url', created_order.proof_url,
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
        if requested_id is null or requested_type not in ('class', 'package') then
            raise exception using errcode = 'P0001', message = 'Item order tidak valid';
        end if;
        if requested_qty is distinct from 1 then
            raise exception using errcode = 'P0001', message = 'Jumlah item harus 1';
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
              and c.archived_at is null
              and co.id = requested_offer_id and co.visible = true;
        elsif requested_type = 'class' then
            select c.title, c.price::bigint, c.price::bigint
            into catalog_title, catalog_price, catalog_list_price
            from public.classes c
            where c.id = requested_id and c.visible = true and c.archived_at is null;
        else
            select p.title, p.price::bigint, p.price::bigint,
                   jsonb_build_object('items', coalesce((
                       select jsonb_agg(jsonb_build_object(
                           'class_id', pi.class_id,
                           'class_title', c.title,
                           'class_offer_id', pi.class_offer_id,
                           'meeting_count', co.meeting_count,
                           'list_price', co.list_price,
                           'price', co.price
                       ) order by pi.created_at, pi.class_id)
                       from public.package_items pi
                       join public.classes c on c.id = pi.class_id
                       join public.class_offers co on co.id = pi.class_offer_id
                       where pi.package_id = p.id
                   ), '[]'::jsonb))
            into catalog_title, catalog_price, catalog_list_price, selected_snapshot
            from public.packages p
            where p.id = requested_id and p.visible = true and p.archived_at is null;
        end if;
        if not found then
            raise exception using errcode = 'P0001', message = 'Item tidak tersedia';
        end if;
        if requested_type = 'package' then
            if jsonb_array_length(selected_snapshot -> 'items') = 0 then
                raise exception using errcode = 'P0001', message = 'Paket ini kosong';
            end if;
            if exists (
                select 1 from public.package_items pi
                join public.classes c on c.id = pi.class_id
                join public.class_offers co on co.id = pi.class_offer_id
                where pi.package_id = requested_id
                  and (c.visible = false or c.archived_at is not null or co.visible = false)
            ) then
                raise exception using errcode = 'P0001', message = 'Item tidak tersedia';
            end if;
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
        join jsonb_array_elements(package_item -> 'offer_snapshot' -> 'items') child
          on child ->> 'class_id' = direct_item ->> 'item_id'
    ) then
        raise exception using errcode = 'P0001', message = 'Kelas duplikat dengan isi bundle';
    end if;

    insert into public.orders (
        user_id, items, total, status, fulfillment_mode, proof_url, sender_name, note
    ) values (
        p_user_id, enriched_items, order_total, 'pending', 'automatic',
        p_proof_path, p_sender_name, p_note
    ) returning * into created_order;

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
        'status', created_order.status,
        'fulfillment_mode', created_order.fulfillment_mode,
        'proof_url', created_order.proof_url,
        'sender_name', created_order.sender_name, 'note', created_order.note,
        'created_at', created_order.created_at
    );
end;
$$;

create or replace function public.admin_paginated_orders(
    p_limit integer, p_offset integer, p_search text, p_status text
)
returns jsonb
language sql
stable
set search_path = public, extensions
as $$
with filtered as materialized (
    select o.id, o.user_id, o.total, o.status, o.fulfillment_mode,
           o.proof_url, o.sender_name, o.note, o.created_at,
           u.full_name as user_name, u.email as user_email
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
        'total', p.total, 'status', p.status,
        'fulfillment_mode', p.fulfillment_mode,
        'proof_url', p.proof_url,
        'sender_name', p.sender_name, 'note', p.note, 'created_at', p.created_at,
        'user_name', p.user_name, 'user_email', p.user_email
    ) order by p.created_at desc, p.id) from page p), '[]'::jsonb)
);
$$;

-- An approved order can later expire without revoking access. Keep such
-- participants visible in the manual enrollment screen while access is active.
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
    select u.id, u.full_name, u.email,
           lower(coalesce(u.full_name, '')) as sort_name
    from public.users u
    where u.role = 'peserta'
      and (
          exists (
              select 1 from public.orders o
              where o.user_id = u.id and o.status = 'approved'
          )
          or exists (
              select 1 from public.enrollments e
              where e.user_id = u.id and e.active = true
          )
      )
      and (
          p_search is null or p_search = ''
          or lower(u.full_name) like '%' || lower(p_search) || '%'
          or lower(u.email::text) like '%' || lower(p_search) || '%'
      )
      and (
          p_after_name is null or p_after_id is null
          or (lower(coalesce(u.full_name, '')), u.id) > (p_after_name, p_after_id)
      )
), page_plus_one as (
    select * from eligible order by sort_name, id
    limit least(greatest(p_limit, 1), 100) + 1
), page as (
    select * from page_plus_one order by sort_name, id
    limit least(greatest(p_limit, 1), 100)
)
select jsonb_build_object(
    'participants', coalesce((
        select jsonb_agg(
            jsonb_build_object('id', id, 'full_name', full_name, 'email', email)
            order by sort_name, id
        ) from page
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

-- Match bootstrap selection to the candidate list after an approved order expires.
create or replace function public.admin_enrollment_bootstrap(
    p_user_id uuid,
    p_search text,
    p_limit integer,
    p_after_name text,
    p_after_id uuid
)
returns jsonb
language plpgsql
stable
set search_path = public
as $$
declare
    candidate_payload jsonb;
    selected_id uuid;
begin
    candidate_payload := public.admin_enrollment_candidates(
        p_search, p_limit, p_after_name, p_after_id);

    if p_user_id is not null and exists (
        select 1 from public.users u
        where u.id = p_user_id and u.role = 'peserta'
          and (
              exists (select 1 from public.orders o
                      where o.user_id = u.id and o.status = 'approved')
              or exists (select 1 from public.enrollments e
                         where e.user_id = u.id and e.active = true)
          )
    ) then
        selected_id := p_user_id;
    elsif jsonb_array_length(candidate_payload -> 'participants') > 0 then
        selected_id := (candidate_payload -> 'participants' -> 0 ->> 'id')::uuid;
    end if;

    return (
        with active_batch as (
            select b.id from public.batches b
            where b.is_active = true
            order by b.created_at desc limit 1
        )
        select jsonb_build_object(
            'participants', candidate_payload -> 'participants',
            'has_more', coalesce((candidate_payload ->> 'has_more')::boolean, false),
            'next_after_name', candidate_payload ->> 'next_after_name',
            'next_after_id', candidate_payload ->> 'next_after_id',
            'classes', coalesce((
                select jsonb_agg(jsonb_build_object(
                    'id', c.id, 'title', c.title,
                    'archived', c.archived_at is not null)
                                 order by c.created_at desc, c.id)
                from public.classes c
                where not exists (select 1 from active_batch)
                   or c.batch_id = (select id from active_batch)
            ), '[]'::jsonb),
            'packages', coalesce((
                select jsonb_agg(jsonb_build_object(
                    'id', p.id, 'title', p.title,
                    'class_ids', coalesce(to_jsonb(p.class_ids), '[]'::jsonb))
                    order by p.created_at desc, p.id)
                from public.packages p
                where p.archived_at is null
                  and (not exists (select 1 from active_batch)
                       or p.batch_id = (select id from active_batch))
            ), '[]'::jsonb),
            'selected_user', (
                select jsonb_build_object('id', u.id, 'full_name', u.full_name,
                                          'email', u.email)
                from public.users u where u.id = selected_id
            ),
            'active_class_ids', coalesce((
                select jsonb_agg(e.class_id order by e.created_at desc, e.class_id)
                from public.enrollments e
                where e.user_id = selected_id and e.active = true
            ), '[]'::jsonb)
        )
    );
end;
$$;

create or replace function public.admin_update_order_status(p_order_id uuid, p_status text)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
    current_order public.orders%rowtype;
    line public.order_items%rowtype;
    child jsonb;
    child_class_id uuid;
    child_offer_id uuid;
    child_title text;
    child_meeting_count integer;
    result jsonb;
begin
    if p_status not in ('approved', 'rejected', 'expired') then
        raise exception using errcode = 'P0001', message = 'Status order tidak valid';
    end if;
    select * into current_order from public.orders where id = p_order_id for update;
    if not found then return null; end if;

    if current_order.status::text <> p_status then
        if current_order.status = 'pending' then
            if p_status = 'approved' and current_order.fulfillment_mode = 'automatic' then
                if not exists (select 1 from public.order_items where order_id = p_order_id) then
                    raise exception using errcode = 'P0001', message = 'Item order tidak lengkap';
                end if;
                for line in select * from public.order_items where order_id = p_order_id order by id
                loop
                    if line.qty <> 1 then
                        raise exception using errcode = 'P0001', message = 'Jumlah item harus 1';
                    end if;
                    if line.item_type = 'class' then
                        if not exists (select 1 from public.classes where id = line.item_id) then
                            raise exception using errcode = 'P0001', message = 'Kelas pesanan sudah tidak tersedia';
                        end if;
                        insert into public.order_enrollment_grants (
                            order_id, order_item_id, user_id, class_id,
                            class_offer_id, class_title, meeting_count
                        ) values (
                            p_order_id, line.id, current_order.user_id, line.item_id,
                            line.offer_id, line.item_title, line.meeting_count
                        ) on conflict (order_item_id, class_id) do nothing;
                        insert into public.enrollments (user_id, class_id, active)
                        values (current_order.user_id, line.item_id, true)
                        on conflict (user_id, class_id) do update set active = true;
                    elsif line.item_type = 'package' then
                        if jsonb_typeof(line.offer_snapshot -> 'items') is distinct from 'array'
                           or jsonb_array_length(line.offer_snapshot -> 'items') = 0 then
                            raise exception using errcode = 'P0001', message = 'Snapshot paket tidak lengkap';
                        end if;
                        for child in select value from jsonb_array_elements(line.offer_snapshot -> 'items')
                        loop
                            begin
                                child_class_id := (child ->> 'class_id')::uuid;
                                child_offer_id := (child ->> 'class_offer_id')::uuid;
                                child_meeting_count := (child ->> 'meeting_count')::integer;
                                child_title := nullif(child ->> 'class_title', '');
                            exception when others then
                                raise exception using errcode = 'P0001', message = 'Snapshot paket tidak lengkap';
                            end;
                            if child_class_id is null or child_offer_id is null
                               or child_title is null
                               or child_meeting_count is null or child_meeting_count <= 0 then
                                raise exception using errcode = 'P0001', message = 'Snapshot paket tidak lengkap';
                            end if;
                            if exists (
                                select 1 from public.order_enrollment_grants
                                where order_item_id = line.id and class_id = child_class_id
                            ) then
                                raise exception using errcode = 'P0001', message = 'Snapshot paket berisi kelas duplikat';
                            end if;
                            if not exists (select 1 from public.classes where id = child_class_id) then
                                raise exception using errcode = 'P0001', message = 'Kelas pesanan sudah tidak tersedia';
                            end if;
                            insert into public.order_enrollment_grants (
                                order_id, order_item_id, user_id, class_id, package_id,
                                class_offer_id, class_title, meeting_count
                            ) values (
                                p_order_id, line.id, current_order.user_id, child_class_id,
                                line.item_id, child_offer_id, child_title, child_meeting_count
                            );
                            insert into public.enrollments (user_id, class_id, active)
                            values (current_order.user_id, child_class_id, true)
                            on conflict (user_id, class_id) do update set active = true;
                        end loop;
                    else
                        raise exception using errcode = 'P0001', message = 'Item order tidak lengkap';
                    end if;
                end loop;
            end if;
        elsif current_order.status = 'approved' and p_status = 'expired' then
            null; -- Expiring an approved order preserves granted access.
        else
            raise exception using errcode = 'P0001', message = 'Perubahan status order tidak diizinkan';
        end if;
        update public.orders
        set status = p_status::public.order_status
        where id = p_order_id;
    end if;

    select jsonb_build_object(
        'id', o.id, 'user_id', o.user_id,
        'items', coalesce((select jsonb_agg(jsonb_build_object(
            'item_id', oi.item_id, 'item_type', oi.item_type,
            'item_title', oi.item_title, 'qty', oi.qty, 'price', oi.unit_price,
            'list_price', oi.list_price, 'offer_id', oi.offer_id,
            'meeting_count', oi.meeting_count, 'offer_snapshot', oi.offer_snapshot
        ) order by oi.id) from public.order_items oi where oi.order_id = o.id), '[]'::jsonb),
        'total', o.total, 'status', o.status,
        'fulfillment_mode', o.fulfillment_mode,
        'proof_url', o.proof_url,
        'sender_name', o.sender_name, 'note', o.note, 'created_at', o.created_at,
        'user_name', u.full_name, 'user_email', u.email
    ) into result from public.orders o left join public.users u on u.id = o.user_id
    where o.id = p_order_id;
    return result;
end;
$$;

revoke all on table public.order_enrollment_grants from public, anon, authenticated;
grant select, insert on table public.order_enrollment_grants to service_role;
grant usage, select on sequence public.order_enrollment_grants_id_seq to service_role;
revoke all on function public.admin_archive_package(uuid) from public, anon, authenticated;
revoke all on function public.admin_archive_class(uuid) from public, anon, authenticated;
grant execute on function public.admin_archive_package(uuid) to service_role;
grant execute on function public.admin_archive_class(uuid) to service_role;
revoke all on function public.admin_enrollment_candidates(text, integer, text, uuid)
    from public, anon, authenticated;
grant execute on function public.admin_enrollment_candidates(text, integer, text, uuid)
    to service_role;
revoke all on function public.admin_enrollment_bootstrap(uuid, text, integer, text, uuid)
    from public, anon, authenticated;
grant execute on function public.admin_enrollment_bootstrap(uuid, text, integer, text, uuid)
    to service_role;

commit;
