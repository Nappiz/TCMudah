begin;

set local lock_timeout = '10s';
set local statement_timeout = '10min';

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
        update public.orders set status = p_status::public.order_status where id = p_order_id returning *
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

commit;
