-- Run against a database with the order migrations applied. The transaction
-- ensures even an accidental UUID collision cannot change a real order.
begin;

do $$
declare
    missing_order_id uuid := gen_random_uuid();
    result jsonb;
begin
    foreach result in array array[
        public.admin_update_order_status(missing_order_id, 'approved'),
        public.admin_update_order_status(missing_order_id, 'rejected'),
        public.admin_update_order_status(missing_order_id, 'expired')
    ] loop
        if result is not null then
            raise exception 'Unexpected order found for test UUID';
        end if;
    end loop;
end;
$$;

rollback;
