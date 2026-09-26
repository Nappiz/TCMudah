-- Execute against an isolated database after fixtures/order_enrollment_baseline.sql
-- and the order-enrollment migration have been applied.
begin;

do $$
declare
    legacy_mode text;
    result jsonb;
begin
    select fulfillment_mode into legacy_mode from public.orders
    where id = '40000000-0000-0000-0000-000000000001';
    if legacy_mode <> 'legacy_manual' then
        raise exception 'Pre-existing order must remain manual';
    end if;
    result := public.admin_update_order_status('40000000-0000-0000-0000-000000000001', 'approved');
    if result ->> 'fulfillment_mode' <> 'legacy_manual' then
        raise exception 'Legacy approval mode is missing';
    end if;
    if (select count(*) from public.order_enrollment_grants) <> 0 then
        raise exception 'Legacy order unexpectedly granted access';
    end if;
    if (select count(*) from public.enrollments where active) <> 1 then
        raise exception 'Existing enrollment changed';
    end if;
    perform public.admin_update_order_status('40000000-0000-0000-0000-000000000001', 'expired');
end;
$$;

insert into public.payment_upload_intents
    (path, user_id, bucket_id, content_type, max_size_bytes, expires_at)
values ('proof-package', '00000000-0000-0000-0000-000000000001', 'payments',
        'image/png', 1024, now() + interval '1 day'),
       ('proof-class', '00000000-0000-0000-0000-000000000001', 'payments',
        'image/png', 1024, now() + interval '1 day'),
       ('proof-direct', '00000000-0000-0000-0000-000000000001', 'payments',
        'image/png', 1024, now() + interval '1 day');
insert into storage.objects (bucket_id, name, metadata) values
    ('payments', 'proof-package', '{"size":512,"mimetype":"image/png"}'),
    ('payments', 'proof-class', '{"size":512,"mimetype":"image/png"}'),
    ('payments', 'proof-direct', '{"size":512,"mimetype":"image/png"}');

create temp table order_test_ids (kind text primary key, id uuid not null);

do $$
declare
    created jsonb;
    package_members jsonb;
begin
    created := public.create_order_transactional(
        '00000000-0000-0000-0000-000000000001',
        '[{"item_id":"30000000-0000-0000-0000-000000000001","item_type":"package","qty":1}]',
        'proof-package', 'payments', 'Peserta Lama', null
    );
    insert into order_test_ids values ('package', (created ->> 'id')::uuid);
    package_members := created -> 'items' -> 0 -> 'offer_snapshot' -> 'items';
    if jsonb_array_length(package_members) <> 2
       or package_members -> 0 ->> 'class_title' <> 'Matematika'
       or package_members -> 1 ->> 'class_title' <> 'Fisika' then
        raise exception 'Checkout did not snapshot package class titles';
    end if;
    if (select fulfillment_mode from public.orders where id = (created ->> 'id')::uuid)
       <> 'automatic' then
        raise exception 'New order must be automatic';
    end if;
end;
$$;

-- Live catalog changes must not affect what the participant purchased.
delete from public.package_items
where package_id = '30000000-0000-0000-0000-000000000001'
  and class_id = '10000000-0000-0000-0000-000000000002';
update public.classes set title = 'Fisika Baru'
where id = '10000000-0000-0000-0000-000000000002';

do $$
declare
    package_order_id uuid := (select id from order_test_ids where kind = 'package');
    result jsonb;
    candidates jsonb;
    bootstrap jsonb;
begin
    result := public.admin_update_order_status(package_order_id, 'approved');
    if result ->> 'status' <> 'approved' then
        raise exception 'Package approval failed';
    end if;
    if (select count(*) from public.order_enrollment_grants where order_id = package_order_id) <> 2 then
        raise exception 'Package approval must grant its original two classes';
    end if;
    if not exists (
        select 1 from public.order_enrollment_grants
        where order_id = package_order_id
          and class_id = '10000000-0000-0000-0000-000000000002'
          and class_title = 'Fisika'
          and package_id = '30000000-0000-0000-0000-000000000001'
          and meeting_count = 4
    ) then
        raise exception 'Purchase origin or class snapshot was lost';
    end if;
    if (select count(*) from public.enrollments where active) <> 2 then
        raise exception 'Automatic package enrollment is incomplete';
    end if;

    perform public.admin_update_order_status(package_order_id, 'approved');
    if (select count(*) from public.order_enrollment_grants where order_id = package_order_id) <> 2 then
        raise exception 'Repeated approval duplicated grants';
    end if;

    update public.enrollments set active = false
    where user_id = '00000000-0000-0000-0000-000000000001'
      and class_id = '10000000-0000-0000-0000-000000000002';
    perform public.admin_update_order_status(package_order_id, 'approved');
    if (select active from public.enrollments
        where user_id = '00000000-0000-0000-0000-000000000001'
          and class_id = '10000000-0000-0000-0000-000000000002') then
        raise exception 'Repeated approval reactivated manually removed access';
    end if;
    update public.enrollments set active = true
    where user_id = '00000000-0000-0000-0000-000000000001'
      and class_id = '10000000-0000-0000-0000-000000000002';

    perform public.admin_update_order_status(package_order_id, 'expired');
    if (select count(*) from public.enrollments where active) <> 2 then
        raise exception 'Order expiration revoked access';
    end if;
    candidates := public.admin_enrollment_candidates(null, 20, null, null);
    if exists (
        select 1 from jsonb_array_elements(candidates -> 'participants') candidate
        where candidate ->> 'id' = '00000000-0000-0000-0000-000000000001'
    ) then
        raise exception 'Participant with only an expired order remains in enrollment candidates';
    end if;
    bootstrap := public.admin_enrollment_bootstrap(
        '00000000-0000-0000-0000-000000000001', 'nobody', 20, null, null);
    if bootstrap -> 'selected_user' ->> 'id' is not null then
        raise exception 'Participant with only an expired order remains selected';
    end if;
end;
$$;

-- Tampering with a stored package snapshot must not silently grant partial access.
do $$
declare
    bad_order uuid := '40000000-0000-0000-0000-000000000003';
    package_items jsonb;
begin
    package_items := jsonb_build_array(jsonb_build_object(
        'class_id', '10000000-0000-0000-0000-000000000001',
        'class_title', 'Matematika', 'meeting_count', 6));
    insert into public.orders (id, user_id, items, total, status, fulfillment_mode)
    values (bad_order, '00000000-0000-0000-0000-000000000001', '[]', 100000, 'pending', 'automatic');
    insert into public.order_items
        (order_id, item_id, item_type, item_title, qty, unit_price, line_total, offer_snapshot)
    values (bad_order, '30000000-0000-0000-0000-000000000001', 'package',
            'Paket Sains', 1, 100000, 100000, jsonb_build_object('items', package_items));
    begin
        perform public.admin_update_order_status(bad_order, 'approved');
        raise exception 'Missing offer identity was approved';
    exception when raise_exception then
        if sqlerrm = 'Missing offer identity was approved' then raise; end if;
    end;
    if (select status from public.orders where id = bad_order) <> 'pending'
       or exists (select 1 from public.order_enrollment_grants where order_id = bad_order) then
        raise exception 'Invalid offer identity left a partial approval';
    end if;

    update public.order_items
    set offer_snapshot = jsonb_build_object('items', jsonb_build_array(
        jsonb_build_object('class_id', '10000000-0000-0000-0000-000000000001',
                           'class_title', 'Matematika',
                           'class_offer_id', '20000000-0000-0000-0000-000000000001',
                           'meeting_count', 6),
        jsonb_build_object('class_id', '10000000-0000-0000-0000-000000000001',
                           'class_title', 'Matematika',
                           'class_offer_id', '20000000-0000-0000-0000-000000000001',
                           'meeting_count', 6)))
    where order_id = bad_order;
    begin
        perform public.admin_update_order_status(bad_order, 'approved');
        raise exception 'Duplicate package class was approved';
    exception when raise_exception then
        if sqlerrm = 'Duplicate package class was approved' then raise; end if;
    end;
    if (select status from public.orders where id = bad_order) <> 'pending'
       or exists (select 1 from public.order_enrollment_grants where order_id = bad_order) then
        raise exception 'Duplicate package class left a partial approval';
    end if;
end;
$$;

do $$
declare
    created jsonb;
    direct_order_id uuid;
begin
    created := public.create_order_transactional(
        '00000000-0000-0000-0000-000000000001',
        '[{"item_id":"10000000-0000-0000-0000-000000000002","item_type":"class","offer_id":"20000000-0000-0000-0000-000000000002","qty":1}]',
        'proof-direct', 'payments', 'Peserta Lama', null
    );
    direct_order_id := (created ->> 'id')::uuid;
    perform public.admin_update_order_status(direct_order_id, 'approved');
    if not exists (
        select 1 from public.order_enrollment_grants
        where order_id = direct_order_id
          and class_id = '10000000-0000-0000-0000-000000000002'
          and package_id is null and meeting_count = 4
          and class_title = 'Fisika Baru'
    ) then
        raise exception 'Direct class order did not record its grant';
    end if;
    if (select count(*) from public.enrollments where active) <> 2 then
        raise exception 'Second purchase duplicated effective enrollment';
    end if;
end;
$$;

insert into public.orders
    (id, user_id, items, total, status, fulfillment_mode)
values (
    '40000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000001',
    '[]', 180000, 'pending', 'automatic'
);
insert into public.order_items
    (order_id, item_id, item_type, item_title, qty, unit_price, line_total)
values (
    '40000000-0000-0000-0000-000000000002',
    '30000000-0000-0000-0000-000000000001',
    'package', 'Paket Sains', 1, 180000, 180000
);

do $$
begin
    begin
        perform public.admin_update_order_status('40000000-0000-0000-0000-000000000002', 'approved');
        raise exception 'Malformed package snapshot was approved';
    exception when raise_exception then
        if sqlerrm = 'Malformed package snapshot was approved' then raise; end if;
    end;
    if (select status from public.orders
        where id = '40000000-0000-0000-0000-000000000002') <> 'pending' then
        raise exception 'Malformed package order left pending state';
    end if;
end;
$$;

do $$
declare
    created jsonb;
    class_order_id uuid;
begin
    created := public.create_order_transactional(
        '00000000-0000-0000-0000-000000000001',
        '[{"item_id":"10000000-0000-0000-0000-000000000003","item_type":"class","offer_id":"20000000-0000-0000-0000-000000000003","qty":1}]',
        'proof-class', 'payments', 'Peserta Lama', null
    );
    class_order_id := (created ->> 'id')::uuid;
    delete from public.classes where id = '10000000-0000-0000-0000-000000000003';
    begin
        perform public.admin_update_order_status(class_order_id, 'approved');
        raise exception 'Missing class was approved';
    exception when foreign_key_violation or raise_exception then
        if sqlerrm = 'Missing class was approved' then raise; end if;
    end;
    if (select status from public.orders where id = class_order_id) <> 'pending'
       or exists (select 1 from public.order_enrollment_grants where order_id = class_order_id) then
        raise exception 'Failed approval left a partial grant or status change';
    end if;
end;
$$;

do $$
declare
    archived jsonb;
    bootstrap jsonb;
begin
    archived := public.admin_archive_class('10000000-0000-0000-0000-000000000001');
    if archived is null
       or (select archived_at is null or visible from public.classes
           where id = '10000000-0000-0000-0000-000000000001')
       or (select archived_at is null or visible from public.packages
           where id = '30000000-0000-0000-0000-000000000001') then
        raise exception 'Class archive did not archive its dependent package';
    end if;
    bootstrap := public.admin_enrollment_bootstrap(
        '00000000-0000-0000-0000-000000000001', null, 20, null, null);
    if exists (
        select 1 from jsonb_array_elements(bootstrap -> 'packages') pkg
        where pkg ->> 'id' = '30000000-0000-0000-0000-000000000001'
    ) then
        raise exception 'Archived package is still assignable from enrollment screen';
    end if;
    if not exists (
        select 1 from jsonb_array_elements(bootstrap -> 'classes') cls
        where cls ->> 'id' = '10000000-0000-0000-0000-000000000001'
          and cls ->> 'archived' = 'true'
    ) then
        raise exception 'Archived enrolled class is missing its management label';
    end if;
end;
$$;

rollback;
