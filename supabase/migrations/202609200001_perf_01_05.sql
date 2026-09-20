begin;

-- Indexes used by the optimized P0 read paths. IF NOT EXISTS keeps the
-- migration safe on projects that already created an equivalent named index.
create index if not exists idx_orders_status_created_at
    on public.orders (status, created_at desc);
create index if not exists idx_orders_created_at
    on public.orders (created_at desc);
create index if not exists idx_orders_user_approved
    on public.orders (user_id)
    where status = 'approved';
create index if not exists idx_users_role_name_id
    on public.users (role, lower(full_name), id);
create index if not exists idx_users_created_at
    on public.users (created_at);
create index if not exists idx_feedbacks_created_at
    on public.feedbacks (created_at);
create index if not exists idx_enrollments_user_active
    on public.enrollments (user_id, active, created_at desc);
create index if not exists idx_classes_batch_created_at
    on public.classes (batch_id, created_at desc);
create index if not exists idx_packages_batch_created_at
    on public.packages (batch_id, created_at desc);


create or replace function public.admin_paginated_users(
    p_limit integer,
    p_offset integer,
    p_search text,
    p_role text
)
returns jsonb
language sql
stable
set search_path = public
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
          or u.full_name ilike '%' || p_search || '%'
          or u.email ilike '%' || p_search || '%'
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
set search_path = public
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
          or u.full_name ilike '%' || p_search || '%'
          or u.email ilike '%' || p_search || '%'
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
            jsonb_build_object(
                'id', id,
                'full_name', full_name,
                'email', email
            )
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
        p_search,
        p_limit,
        p_after_name,
        p_after_id
    );

    if p_user_id is not null and exists (
        select 1
        from public.users u
        where u.id = p_user_id
          and u.role = 'peserta'
          and exists (
              select 1
              from public.orders o
              where o.user_id = u.id
                and o.status = 'approved'
          )
    ) then
        selected_id := p_user_id;
    elsif jsonb_array_length(candidate_payload -> 'participants') > 0 then
        selected_id := (candidate_payload -> 'participants' -> 0 ->> 'id')::uuid;
    end if;

    return (
        with active_batch as (
            select b.id
            from public.batches b
            where b.is_active = true
            order by b.created_at desc
            limit 1
        )
        select jsonb_build_object(
            'participants', candidate_payload -> 'participants',
            'has_more', coalesce((candidate_payload ->> 'has_more')::boolean, false),
            'next_after_name', candidate_payload ->> 'next_after_name',
            'next_after_id', candidate_payload ->> 'next_after_id',
            'classes', coalesce((
                select jsonb_agg(
                    jsonb_build_object('id', c.id, 'title', c.title)
                    order by c.created_at desc, c.id
                )
                from public.classes c
                where not exists (select 1 from active_batch)
                   or c.batch_id = (select id from active_batch)
            ), '[]'::jsonb),
            'packages', coalesce((
                select jsonb_agg(
                    jsonb_build_object(
                        'id', p.id,
                        'title', p.title,
                        'class_ids', coalesce(to_jsonb(p.class_ids), '[]'::jsonb)
                    )
                    order by p.created_at desc, p.id
                )
                from public.packages p
                where not exists (select 1 from active_batch)
                   or p.batch_id = (select id from active_batch)
            ), '[]'::jsonb),
            'selected_user', (
                select jsonb_build_object(
                    'id', u.id,
                    'full_name', u.full_name,
                    'email', u.email
                )
                from public.users u
                where u.id = selected_id
            ),
            'active_class_ids', coalesce((
                select jsonb_agg(e.class_id order by e.created_at desc, e.class_id)
                from public.enrollments e
                where e.user_id = selected_id
                  and e.active = true
            ), '[]'::jsonb)
        )
    );
end;
$$;


create or replace function public.admin_notification_summary(
    p_last_seen_users timestamptz,
    p_last_seen_feedbacks timestamptz
)
returns jsonb
language sql
stable
set search_path = public
as $$
select jsonb_build_object(
    'new_orders', (select count(*) from public.orders where status = 'pending'),
    'new_users', case
        when p_last_seen_users is null then 0
        else (select count(*) from public.users where created_at > p_last_seen_users)
    end,
    'new_feedbacks', case
        when p_last_seen_feedbacks is null then 0
        else (select count(*) from public.feedbacks where created_at > p_last_seen_feedbacks)
    end
);
$$;


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
        coalesce(sum(total) filter (
            where status = 'approved'
              and created_at >= now() - interval '30 days'
        ), 0) as revenue_30d,
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
    select
        o.id,
        o.user_id,
        u.full_name as user_name,
        u.email as user_email,
        o.sender_name,
        o.total,
        o.status,
        o.created_at
    from public.orders o
    left join public.users u on u.id = o.user_id
    where o.status = 'pending'
    order by o.created_at desc, o.id
    limit 5
),
recent_order_rows as (
    select
        o.id,
        o.user_id,
        u.full_name as user_name,
        u.email as user_email,
        o.sender_name,
        o.total,
        o.status,
        o.created_at
    from public.orders o
    left join public.users u on u.id = o.user_id
    order by o.created_at desc, o.id
    limit 15
),
period_items as (
    select
        o.status,
        item,
        coalesce(item ->> 'item_id', item ->> 'class_id') as item_id,
        coalesce(item ->> 'item_type', 'class') as item_type,
        coalesce(nullif(item ->> 'qty', '')::numeric, 0) as qty,
        coalesce(nullif(item ->> 'price', '')::numeric, 0) as price
    from period_orders o
    cross join lateral jsonb_array_elements(coalesce(o.items::jsonb, '[]'::jsonb)) item
),
top_class_rows as (
    select
        pi.item_id as id,
        coalesce(max(pi.item ->> 'item_title'), max(c.title), 'Unknown') as title,
        sum(pi.qty)::bigint as count,
        sum(pi.qty * pi.price)::bigint as revenue
    from period_items pi
    left join public.classes c on c.id::text = pi.item_id
    where pi.status = 'approved'
      and pi.item_type = 'class'
      and pi.item_id is not null
    group by pi.item_id
    order by revenue desc, id
    limit 5
),
revenue_split as (
    select
        coalesce(sum(qty * price) filter (
            where status = 'approved' and item_type = 'class'
        ), 0)::bigint as class_revenue,
        coalesce(sum(qty * price) filter (
            where status = 'approved' and item_type = 'package'
        ), 0)::bigint as package_revenue
    from period_items
)
select jsonb_build_object(
    'stats', (
        select jsonb_build_object(
            'total_users', us.total_users,
            'superadmin', us.superadmin,
            'admin', us.admin,
            'mentor', us.mentor,
            'peserta', us.peserta,
            'new_users_30d', us.new_users_30d,
            'total_curriculum', cs.total_curriculum,
            'total_testimonials', cs.total_testimonials,
            'visible_testimonials', cs.visible_testimonials,
            'hidden_testimonials', cs.total_testimonials - cs.visible_testimonials,
            'total_mentors', cs.total_mentors,
            'visible_mentors', cs.visible_mentors,
            'total_classes', cs.total_classes,
            'visible_classes', cs.visible_classes,
            'class_per_mentor', case
                when cs.total_mentors = 0 then 0
                else cs.total_classes::numeric / cs.total_mentors
            end,
            'total_orders', gos.total_orders,
            'pending_orders', gos.pending_orders,
            'approved_orders', gos.approved_orders,
            'rejected_orders', gos.rejected_orders,
            'expired_orders', gos.expired_orders,
            'revenue_approved', gos.revenue_approved,
            'revenue_30d', gos.revenue_30d,
            'participants_active', gos.participants_active,
            'aov', case
                when gos.approved_orders = 0 then 0
                else gos.revenue_approved::numeric / gos.approved_orders
            end,
            'approval_rate', case
                when gos.total_orders = 0 then 0
                else round(gos.approved_orders::numeric * 100 / gos.total_orders)
            end,
            'order_series', coalesce((
                select jsonb_agg(
                    jsonb_build_object('key', day::text, 'value', order_count)
                    order by day
                )
                from series
            ), '[]'::jsonb),
            'revenue_series', coalesce((
                select jsonb_agg(
                    jsonb_build_object('key', day::text, 'value', revenue)
                    order by day
                )
                from series
            ), '[]'::jsonb)
        )
        from user_stats us
        cross join content_stats cs
        cross join global_order_stats gos
    ),
    'period', (
        select jsonb_build_object(
            'total_orders', pos.total_orders,
            'pending_orders', pos.pending_orders,
            'approved_orders', pos.approved_orders,
            'rejected_orders', pos.rejected_orders,
            'expired_orders', pos.expired_orders,
            'revenue_approved', pos.revenue_approved,
            'aov', case
                when pos.approved_orders = 0 then 0
                else pos.revenue_approved::numeric / pos.approved_orders
            end,
            'approval_rate', case
                when pos.total_orders = 0 then 0
                else round(pos.approved_orders::numeric * 100 / pos.total_orders)
            end,
            'class_revenue', rs.class_revenue,
            'package_revenue', rs.package_revenue,
            'top_classes', coalesce((
                select jsonb_agg(
                    jsonb_build_object(
                        'id', id,
                        'title', title,
                        'count', count,
                        'revenue', revenue
                    )
                    order by revenue desc, id
                )
                from top_class_rows
            ), '[]'::jsonb)
        )
        from period_order_stats pos
        cross join revenue_split rs
    ),
    'pending_latest', coalesce((
        select jsonb_agg(to_jsonb(por) order by por.created_at desc, por.id)
        from pending_order_rows por
    ), '[]'::jsonb),
    'recent_orders', coalesce((
        select jsonb_agg(to_jsonb(ror) order by ror.created_at desc, ror.id)
        from recent_order_rows ror
    ), '[]'::jsonb)
);
$$;


revoke all on function public.admin_paginated_users(integer, integer, text, text)
    from public, anon, authenticated;
revoke all on function public.admin_enrollment_candidates(text, integer, text, uuid)
    from public, anon, authenticated;
revoke all on function public.admin_enrollment_bootstrap(uuid, text, integer, text, uuid)
    from public, anon, authenticated;
revoke all on function public.admin_notification_summary(timestamptz, timestamptz)
    from public, anon, authenticated;
revoke all on function public.admin_dashboard_overview(timestamptz, timestamptz, integer)
    from public, anon, authenticated;

grant execute on function public.admin_paginated_users(integer, integer, text, text)
    to service_role;
grant execute on function public.admin_enrollment_candidates(text, integer, text, uuid)
    to service_role;
grant execute on function public.admin_enrollment_bootstrap(uuid, text, integer, text, uuid)
    to service_role;
grant execute on function public.admin_notification_summary(timestamptz, timestamptz)
    to service_role;
grant execute on function public.admin_dashboard_overview(timestamptz, timestamptz, integer)
    to service_role;

commit;
