begin;

-- Expiring an order preserves the participant's existing enrollment access,
-- but an expired order must not keep the participant in the manual enrollment
-- candidate list. A separate approved order can still make the participant
-- eligible.
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
      and exists (
          select 1 from public.orders o
          where o.user_id = u.id and o.status = 'approved'
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
          and exists (
              select 1 from public.orders o
              where o.user_id = u.id and o.status = 'approved'
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

revoke all on function public.admin_enrollment_candidates(text, integer, text, uuid)
    from public, anon, authenticated;
grant execute on function public.admin_enrollment_candidates(text, integer, text, uuid)
    to service_role;
revoke all on function public.admin_enrollment_bootstrap(uuid, text, integer, text, uuid)
    from public, anon, authenticated;
grant execute on function public.admin_enrollment_bootstrap(uuid, text, integer, text, uuid)
    to service_role;

commit;
