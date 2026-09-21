begin;

set local lock_timeout = '10s';
set local statement_timeout = '10min';
set local search_path = public, extensions;

-- Fail loudly when uniqueness cannot be introduced without a business decision.
do $$
begin
    if exists (
        select 1 from public.users
        group by lower(trim(email::text)) having count(*) > 1
    ) then
        raise exception using errcode = 'P0001',
            message = 'Migration dibatalkan: email user duplikat setelah normalisasi';
    end if;
    if exists (
        select 1 from public.shortlinks
        group by lower(trim(slug)) having count(*) > 1
    ) then
        raise exception using errcode = 'P0001',
            message = 'Migration dibatalkan: slug shortlink duplikat setelah normalisasi';
    end if;
    if exists (
        select 1 from public.shortlinks
        where lower(trim(slug)) !~ '^[a-z0-9_-]+$'
    ) then
        raise exception using errcode = 'P0001',
            message = 'Migration dibatalkan: slug shortlink legacy tidak valid';
    end if;
    if exists (
        select 1 from public.app_settings group by key having count(*) > 1
    ) then
        raise exception using errcode = 'P0001',
            message = 'Migration dibatalkan: key app_settings duplikat';
    end if;
    if exists (
        select 1 from public.orders where proof_url is not null
        group by proof_url having count(*) > 1
    ) then
        raise exception using errcode = 'P0001',
            message = 'Migration dibatalkan: bukti pembayaran dipakai lebih dari satu order';
    end if;
end;
$$;

update public.users set email = lower(trim(email::text))
where email::text is distinct from lower(trim(email::text));
update public.shortlinks set slug = lower(trim(slug))
where slug is distinct from lower(trim(slug));

-- Consolidate feedback duplicates before enforcing idempotent upsert semantics.
with ranked as (
    select id, row_number() over (
        partition by user_id, class_id order by created_at desc, id desc
    ) as row_number
    from public.feedbacks
)
delete from public.feedbacks f using ranked r
where f.id = r.id and r.row_number > 1;

-- Keep the newest active batch if historical writes created more than one.
with ranked as (
    select id, row_number() over (order by created_at desc, id desc) as row_number
    from public.batches where is_active = true
)
update public.batches b set is_active = false
from ranked r where b.id = r.id and r.row_number > 1;

-- Verified indexes and constraints for the concrete access patterns in PERF-11..15.
create unique index if not exists uq_users_email_normalized
    on public.users (lower(email::text));
create index if not exists idx_users_role_created_at
    on public.users (role, created_at desc);
create index if not exists idx_orders_status_created_at
    on public.orders (status, created_at desc);
-- The earlier PERF migrations already cover approved orders and active
-- enrollments. Do not create equivalent indexes under new names.
create index if not exists idx_classes_batch_visible_created
    on public.classes (batch_id, visible, created_at desc);
create index if not exists idx_packages_batch_visible_created
    on public.packages (batch_id, visible, created_at desc);
create index if not exists idx_materials_class_visible_created
    on public.class_materials (class_id, visible, created_at desc);
create unique index if not exists uq_feedbacks_user_class
    on public.feedbacks (user_id, class_id);
create index if not exists idx_feedbacks_created_at
    on public.feedbacks (created_at desc);
create unique index if not exists uq_shortlinks_slug_normalized
    on public.shortlinks (lower(slug));
do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.shortlinks'::regclass
          and conname = 'ck_shortlinks_slug_format'
    ) then
        alter table public.shortlinks
            add constraint ck_shortlinks_slug_format
            check (slug ~ '^[a-z0-9_-]+$') not valid;
    end if;
end;
$$;
alter table public.shortlinks validate constraint ck_shortlinks_slug_format;
create unique index if not exists uq_batches_single_active
    on public.batches ((is_active)) where is_active = true;
create unique index if not exists uq_app_settings_key
    on public.app_settings (key);
create unique index if not exists uq_orders_proof_path
    on public.orders (proof_url) where proof_url is not null;


-- One-call access check plus material projection.
create or replace function public.get_authorized_materials(
    p_user_id uuid,
    p_class_id uuid,
    p_is_staff boolean
)
returns jsonb
language plpgsql
stable
set search_path = public
as $$
begin
    if not coalesce(p_is_staff, false) and not exists (
        select 1 from public.enrollments e
        where e.user_id = p_user_id
          and e.class_id = p_class_id
          and e.active = true
    ) then
        raise exception using errcode = 'P0001', message = 'Tidak punya akses ke kelas ini';
    end if;

    return coalesce((
        select jsonb_agg(
            jsonb_build_object(
                'id', m.id,
                'class_id', m.class_id,
                'title', m.title,
                'url', m.url,
                'visible', m.visible,
                'type', m.type,
                'batch_id', m.batch_id,
                'created_at', m.created_at
            ) order by m.created_at desc, m.id
        )
        from public.class_materials m
        where m.class_id = p_class_id and m.visible = true
    ), '[]'::jsonb);
end;
$$;


-- Access check and feedback upsert are one transaction and one round-trip.
create or replace function public.submit_feedback(
    p_user_id uuid,
    p_class_id uuid,
    p_is_staff boolean,
    p_text text,
    p_rating integer
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
    result public.feedbacks%rowtype;
begin
    if not coalesce(p_is_staff, false) and not exists (
        select 1 from public.enrollments e
        where e.user_id = p_user_id
          and e.class_id = p_class_id
          and e.active = true
    ) then
        raise exception using errcode = 'P0001', message = 'Tidak punya akses ke kelas ini';
    end if;

    insert into public.feedbacks (user_id, class_id, text, rating)
    values (p_user_id, p_class_id, p_text, p_rating)
    on conflict (user_id, class_id) do update
    set text = excluded.text, rating = excluded.rating
    returning * into result;

    return jsonb_build_object(
        'id', result.id,
        'class_id', result.class_id,
        'text', result.text,
        'rating', result.rating,
        'created_at', result.created_at
    );
end;
$$;


-- Batch activation is serialized by the partial unique index and one transaction.
create or replace function public.admin_create_batch(
    p_name text,
    p_is_active boolean
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
    result public.batches%rowtype;
begin
    if coalesce(p_is_active, false) then
        perform pg_advisory_xact_lock(hashtext('tcmudah-active-batch'));
        update public.batches set is_active = false where is_active = true;
    end if;
    insert into public.batches (name, is_active)
    values (p_name, coalesce(p_is_active, false))
    returning * into result;
    return to_jsonb(result);
end;
$$;

create or replace function public.admin_update_batch(
    p_batch_id uuid,
    p_patch jsonb
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
    result public.batches%rowtype;
begin
    if coalesce((p_patch ->> 'is_active')::boolean, false) then
        perform pg_advisory_xact_lock(hashtext('tcmudah-active-batch'));
        update public.batches
        set is_active = false
        where is_active = true and id <> p_batch_id;
    end if;

    update public.batches
    set name = case when p_patch ? 'name' then p_patch ->> 'name' else name end,
        is_active = case
            when p_patch ? 'is_active' then (p_patch ->> 'is_active')::boolean
            else is_active
        end
    where id = p_batch_id
    returning * into result;

    if not found then return null; end if;
    return to_jsonb(result);
end;
$$;


-- Atomic redirect resolution prevents lost click increments under concurrency.
create or replace function public.resolve_shortlink(p_slug text)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
    result jsonb;
begin
    with updated as (
        update public.shortlinks
        set clicks = coalesce(clicks, 0) + 1
        where lower(slug) = lower(trim(p_slug)) and active = true
        returning url, clicks
    )
    select jsonb_build_object('url', url, 'clicks', clicks)
    into result from updated;
    return result;
end;
$$;


-- Upload intent binds a private Storage object to one user and one order submission.
create table if not exists public.payment_upload_intents (
    path text primary key,
    user_id uuid not null references public.users(id) on delete cascade,
    bucket_id text not null,
    content_type text not null check (content_type in ('image/jpeg', 'image/png', 'image/webp')),
    max_size_bytes bigint not null check (max_size_bytes between 1 and 5242880),
    expires_at timestamptz not null,
    consumed_at timestamptz,
    created_at timestamptz not null default now()
);
create index if not exists idx_payment_upload_intents_expiry
    on public.payment_upload_intents (expires_at) where consumed_at is null;

create or replace function public.create_payment_upload_intent(
    p_path text,
    p_user_id uuid,
    p_bucket_id text,
    p_content_type text,
    p_max_size_bytes bigint,
    p_expires_at timestamptz
)
returns jsonb
language plpgsql
set search_path = public, storage
as $$
begin
    if not exists (
        select 1 from storage.buckets b
        where b.id = p_bucket_id and b.public = false
    ) then
        raise exception using errcode = 'P0001',
            message = 'Bucket bukti pembayaran harus private';
    end if;

    insert into public.payment_upload_intents (
        path, user_id, bucket_id, content_type, max_size_bytes, expires_at
    ) values (
        p_path, p_user_id, p_bucket_id, p_content_type,
        p_max_size_bytes, p_expires_at
    );
    return jsonb_build_object('path', p_path, 'expires_at', p_expires_at);
end;
$$;

drop function if exists public.create_order_transactional(uuid, jsonb, text, text, text);
create function public.create_order_transactional(
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
    requested_type text;
    requested_qty integer;
    catalog_title text;
    catalog_price bigint;
    enriched_items jsonb := '[]'::jsonb;
    order_total bigint := 0;
    created_order public.orders%rowtype;
    upload_intent public.payment_upload_intents%rowtype;
    uploaded_size bigint;
    uploaded_type text;
begin
    select * into created_order
    from public.orders
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

    select * into upload_intent
    from public.payment_upload_intents
    where path = p_proof_path and user_id = p_user_id and bucket_id = p_proof_bucket
    for update;

    if not found then
        raise exception using errcode = 'P0001', message = 'Bukti pembayaran tidak valid atau kedaluwarsa';
    end if;

    -- A concurrent retry can pass the optimistic lookup above and wait on this
    -- intent lock. Return the order created by the winning transaction instead
    -- of turning a safe retry into an error.
    if upload_intent.consumed_at is not null then
        select * into created_order
        from public.orders
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
    into uploaded_size, uploaded_type
    from storage.objects
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
        exception when others then
            raise exception using errcode = 'P0001', message = 'Format item order tidak valid';
        end;
        requested_type := coalesce(source_item ->> 'item_type', 'class');
        if requested_id is null or requested_qty is null
           or requested_type not in ('class', 'package')
           or requested_qty not between 1 and 99 then
            raise exception using errcode = 'P0001', message = 'Item order tidak valid';
        end if;

        if requested_type = 'class' then
            select title, price::bigint into catalog_title, catalog_price
            from public.classes where id = requested_id and visible = true;
        else
            select title, price::bigint into catalog_title, catalog_price
            from public.packages where id = requested_id and visible = true;
        end if;
        if not found then
            raise exception using errcode = 'P0001', message = 'Item tidak tersedia';
        end if;

        enriched_items := enriched_items || jsonb_build_array(jsonb_build_object(
            'item_id', requested_id, 'item_type', requested_type,
            'item_title', catalog_title, 'qty', requested_qty, 'price', catalog_price
        ));
        order_total := order_total + catalog_price * requested_qty;
    end loop;

    insert into public.orders (user_id, items, total, status, proof_url, sender_name, note)
    values (p_user_id, enriched_items, order_total, 'pending', p_proof_path, p_sender_name, p_note)
    returning * into created_order;

    insert into public.order_items (
        order_id, item_id, item_type, item_title, qty, unit_price, line_total
    )
    select created_order.id, (item ->> 'item_id')::uuid, item ->> 'item_type',
           item ->> 'item_title', (item ->> 'qty')::integer,
           (item ->> 'price')::bigint,
           (item ->> 'qty')::integer * (item ->> 'price')::bigint
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


revoke all on table public.payment_upload_intents from public, anon, authenticated;
grant all on table public.payment_upload_intents to service_role;

revoke all on function public.get_authorized_materials(uuid, uuid, boolean) from public, anon, authenticated;
revoke all on function public.submit_feedback(uuid, uuid, boolean, text, integer) from public, anon, authenticated;
revoke all on function public.admin_create_batch(text, boolean) from public, anon, authenticated;
revoke all on function public.admin_update_batch(uuid, jsonb) from public, anon, authenticated;
revoke all on function public.resolve_shortlink(text) from public, anon, authenticated;
revoke all on function public.create_payment_upload_intent(text, uuid, text, text, bigint, timestamptz) from public, anon, authenticated;
revoke all on function public.create_order_transactional(uuid, jsonb, text, text, text, text) from public, anon, authenticated;

grant execute on function public.get_authorized_materials(uuid, uuid, boolean) to service_role;
grant execute on function public.submit_feedback(uuid, uuid, boolean, text, integer) to service_role;
grant execute on function public.admin_create_batch(text, boolean) to service_role;
grant execute on function public.admin_update_batch(uuid, jsonb) to service_role;
grant execute on function public.resolve_shortlink(text) to service_role;
grant execute on function public.create_payment_upload_intent(text, uuid, text, text, bigint, timestamptz) to service_role;
grant execute on function public.create_order_transactional(uuid, jsonb, text, text, text, text) to service_role;

commit;
