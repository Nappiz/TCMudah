set local lock_timeout = '10s';
set local statement_timeout = '10min';

-- Keep offer IDs stable because bundles reference them, while allowing two
-- existing offers to exchange meeting_count values without hitting the unique
-- constraint halfway through the update. The function itself is one database
-- transaction, so temporary values are never committed or exposed.
create or replace function public.admin_sync_class_offers(
    p_class_id uuid,
    p_offers jsonb
)
returns jsonb
language plpgsql
set search_path = public
as $$
begin
    if p_offers is null or jsonb_typeof(p_offers) <> 'array' then
        raise exception using
            errcode = 'P0001',
            message = 'Pilihan pertemuan harus berisi 1 sampai 20 item';
    end if;

    if jsonb_array_length(p_offers) = 0
       or jsonb_array_length(p_offers) > 20 then
        raise exception using
            errcode = 'P0001',
            message = 'Pilihan pertemuan harus berisi 1 sampai 20 item';
    end if;

    -- Serialize concurrent edits to the same class.
    perform 1 from public.classes where id = p_class_id for update;
    if not found then
        return null;
    end if;

    if exists (
        select 1
        from jsonb_array_elements(p_offers) offer
        where nullif(offer ->> 'id', '') is not null
          and not exists (
              select 1
              from public.class_offers existing
              where existing.id = (offer ->> 'id')::uuid
                and existing.class_id = p_class_id
          )
    ) then
        raise exception using
            errcode = 'P0001',
            message = 'Pilihan pertemuan tidak termasuk dalam kelas ini';
    end if;

    if exists (
        select 1
        from jsonb_array_elements(p_offers) offer
        group by (offer ->> 'meeting_count')::integer
        having count(*) > 1
    ) then
        raise exception using
            errcode = 'P0001',
            message = 'Jumlah pertemuan dalam satu kelas tidak boleh duplikat';
    end if;

    if (
        select count(*)
        from jsonb_array_elements(p_offers) offer
        where coalesce((offer ->> 'is_recommended')::boolean, false)
    ) > 1 then
        raise exception using
            errcode = 'P0001',
            message = 'Hanya satu pilihan yang boleh direkomendasikan';
    end if;

    if exists (
        select 1
        from public.class_offers existing
        join public.package_items item
          on item.class_offer_id = existing.id
        where existing.class_id = p_class_id
          and not exists (
              select 1
              from jsonb_array_elements(p_offers) offer
              where nullif(offer ->> 'id', '') = existing.id::text
          )
    ) then
        raise exception using
            errcode = 'P0001',
            message = 'Pilihan pertemuan masih digunakan oleh bundle dan tidak dapat dihapus';
    end if;

    -- Removed rows must be cleared first because a newly added offer may reuse
    -- their meeting count. The reference check above keeps bundle links safe.
    delete from public.class_offers existing
    where existing.class_id = p_class_id
      and not exists (
          select 1
          from jsonb_array_elements(p_offers) offer
          where nullif(offer ->> 'id', '') = existing.id::text
      );

    -- Free the partial unique index before choosing the new recommendation.
    update public.class_offers
    set is_recommended = false
    where class_id = p_class_id and is_recommended = true;

    -- Move every changed existing offer to an unused valid count. There are at
    -- most 20 offers and 100 valid counts, so enough staging values always
    -- remain even when current and desired values do not overlap.
    with desired as (
        select
            (offer ->> 'id')::uuid as id,
            (offer ->> 'meeting_count')::integer as meeting_count
        from jsonb_array_elements(p_offers) offer
        where nullif(offer ->> 'id', '') is not null
    ),
    changed as (
        select
            existing.id,
            row_number() over (order by existing.id) as position
        from public.class_offers existing
        join desired on desired.id = existing.id
        where existing.class_id = p_class_id
          and existing.meeting_count <> desired.meeting_count
    ),
    available as (
        select
            candidate,
            row_number() over (order by candidate) as position
        from generate_series(1, 100) as candidates(candidate)
        where not exists (
            select 1
            from public.class_offers existing
            where existing.class_id = p_class_id
              and existing.meeting_count = candidate
        )
          and not exists (
              select 1
              from jsonb_array_elements(p_offers) offer
              where (offer ->> 'meeting_count')::integer = candidate
          )
    ),
    staging as (
        select changed.id, available.candidate as meeting_count
        from changed
        join available using (position)
    )
    update public.class_offers existing
    set meeting_count = staging.meeting_count
    from staging
    where existing.id = staging.id;

    with desired as (
        select
            (offer ->> 'id')::uuid as id,
            (offer ->> 'meeting_count')::integer as meeting_count,
            (offer ->> 'list_price')::bigint as list_price,
            (offer ->> 'price')::bigint as price,
            coalesce((offer ->> 'is_recommended')::boolean, false) as is_recommended,
            coalesce((offer ->> 'visible')::boolean, true) as visible,
            coalesce((offer ->> 'sort_order')::integer, 0) as sort_order
        from jsonb_array_elements(p_offers) offer
        where nullif(offer ->> 'id', '') is not null
    )
    update public.class_offers existing
    set meeting_count = desired.meeting_count,
        list_price = desired.list_price,
        price = desired.price,
        is_recommended = desired.is_recommended,
        visible = desired.visible,
        sort_order = desired.sort_order
    from desired
    where existing.id = desired.id
      and existing.class_id = p_class_id;

    insert into public.class_offers (
        class_id,
        meeting_count,
        list_price,
        price,
        is_recommended,
        visible,
        sort_order
    )
    select
        p_class_id,
        (offer ->> 'meeting_count')::integer,
        (offer ->> 'list_price')::bigint,
        (offer ->> 'price')::bigint,
        coalesce((offer ->> 'is_recommended')::boolean, false),
        coalesce((offer ->> 'visible')::boolean, true),
        coalesce((offer ->> 'sort_order')::integer, 0)
    from jsonb_array_elements(p_offers) offer
    where nullif(offer ->> 'id', '') is null;

    return jsonb_build_object('ok', true);
end;
$$;

revoke all on function public.admin_sync_class_offers(uuid, jsonb)
from public, anon, authenticated;
grant execute on function public.admin_sync_class_offers(uuid, jsonb)
to service_role;
