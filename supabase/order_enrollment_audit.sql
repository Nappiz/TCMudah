-- Read-only cutover audit. Run after 202609250004_order_enrollment.sql.
-- The results identify orders for human reconciliation; this script does not
-- grant or revoke access.

select fulfillment_mode, status, count(*) as orders
from public.orders
group by fulfillment_mode, status
order by fulfillment_mode, status;

-- Old pending orders keep the manual fulfillment workflow.
select o.id, o.user_id, o.created_at,
       count(oi.id) as line_items,
       count(oi.id) filter (
           where oi.item_type = 'package'
             and jsonb_typeof(oi.offer_snapshot -> 'items') is distinct from 'array'
       ) as packages_without_snapshot
from public.orders o
left join public.order_items oi on oi.order_id = o.id
where o.fulfillment_mode = 'legacy_manual' and o.status = 'pending'
group by o.id, o.user_id, o.created_at
order by o.created_at;

-- Approved direct-class orders whose class is currently missing or inactive.
-- These are audit candidates, not automatic backfill instructions.
select o.id as order_id, o.user_id, oi.item_id as class_id,
       oi.item_title, e.active as enrollment_active
from public.orders o
join public.order_items oi on oi.order_id = o.id and oi.item_type = 'class'
left join public.enrollments e
  on e.user_id = o.user_id and e.class_id = oi.item_id
where o.fulfillment_mode = 'legacy_manual'
  and o.status = 'approved'
  and coalesce(e.active, false) = false
order by o.created_at, o.id;

-- Historical package contents can only be reconciled when a checkout
-- snapshot exists. Older packages without it remain unattributed.
select o.id as order_id, o.user_id, oi.item_id as package_id,
       oi.item_title,
       case when jsonb_typeof(oi.offer_snapshot -> 'items') = 'array'
            then jsonb_array_length(oi.offer_snapshot -> 'items')
            else null end as recorded_classes
from public.orders o
join public.order_items oi on oi.order_id = o.id and oi.item_type = 'package'
where o.fulfillment_mode = 'legacy_manual' and o.status = 'approved'
order by o.created_at, o.id;
