-- 0007: deterministic demo orders for the Phase-3 frontend + demo script (O2
-- resolved: seeded fixtures, not free-form mock). All use email demo@lily.test so
-- the demo only varies the order number (order#+email pair still required, NFR-13).
-- Items soft-link to real catalog parts when present (part_id NULL otherwise).
-- Idempotent: each order seeds only if its number is new (CTE returns no row on
-- conflict, so its items/events are skipped too).
--
-- Demo pairs (order_number, email):
--   LILY-1001 / demo@lily.test  — SHIPPED, UPS tracking
--   LILY-1002 / demo@lily.test  — DELIVERED, FedEx, full timeline
--   LILY-1003 / demo@lily.test  — PROCESSING, no tracking yet, 2 items
--   LILY-1004 / demo@lily.test  — RETURN_REQUESTED (was delivered)

-- 1) SHIPPED with tracking
WITH o AS (
  INSERT INTO commerce.orders
    (order_number, email, status, placed_at, carrier, tracking_number,
     shipping_city, shipping_region, total_usd)
  VALUES ('LILY-1001', 'demo@lily.test', 'shipped', '2026-06-08 14:30:00+00',
          'UPS', '1Z999AA10123456784', 'Austin', 'TX', 47.40)
  ON CONFLICT (order_number_norm) DO NOTHING RETURNING order_id
), ins_items AS (
  INSERT INTO commerce.order_items (order_id, part_id, ps_number, name, unit_price_usd, quantity)
  SELECT o.order_id,
         (SELECT part_id FROM catalog.parts WHERE ps_number_norm = catalog.norm_id('PS11752778')),
         'PS11752778', 'Refrigerator Door Shelf Bin', 47.40, 1
  FROM o
)
INSERT INTO commerce.order_events (order_id, event_type, occurred_at, description)
SELECT o.order_id, e.event_type, e.occurred_at, e.description
FROM o, (VALUES
  ('placed',     '2026-06-08 14:30:00+00'::timestamptz, 'Order placed'),
  ('processing', '2026-06-08 18:05:00+00'::timestamptz, 'Preparing your order'),
  ('shipped',    '2026-06-09 09:15:00+00'::timestamptz, 'Shipped via UPS')
) AS e(event_type, occurred_at, description);

-- 2) DELIVERED, full timeline
WITH o AS (
  INSERT INTO commerce.orders
    (order_number, email, status, placed_at, carrier, tracking_number,
     shipping_city, shipping_region, total_usd)
  VALUES ('LILY-1002', 'demo@lily.test', 'delivered', '2026-06-01 10:00:00+00',
          'FedEx', '770123456789', 'Denver', 'CO', 19.24)
  ON CONFLICT (order_number_norm) DO NOTHING RETURNING order_id
), ins_items AS (
  INSERT INTO commerce.order_items (order_id, part_id, ps_number, name, unit_price_usd, quantity)
  SELECT o.order_id,
         (SELECT part_id FROM catalog.parts WHERE ps_number_norm = catalog.norm_id('PS11746591')),
         'PS11746591', 'Dishwasher Rack Track Stop', 9.62, 2
  FROM o
)
INSERT INTO commerce.order_events (order_id, event_type, occurred_at, description)
SELECT o.order_id, e.event_type, e.occurred_at, e.description
FROM o, (VALUES
  ('placed',           '2026-06-01 10:00:00+00'::timestamptz, 'Order placed'),
  ('processing',       '2026-06-01 13:20:00+00'::timestamptz, 'Preparing your order'),
  ('shipped',          '2026-06-02 08:40:00+00'::timestamptz, 'Shipped via FedEx'),
  ('out_for_delivery', '2026-06-04 07:10:00+00'::timestamptz, 'Out for delivery'),
  ('delivered',        '2026-06-04 15:32:00+00'::timestamptz, 'Delivered, left at front door')
) AS e(event_type, occurred_at, description);

-- 3) PROCESSING, no tracking yet, two items
WITH o AS (
  INSERT INTO commerce.orders
    (order_number, email, status, placed_at, shipping_city, shipping_region, total_usd)
  VALUES ('LILY-1003', 'demo@lily.test', 'processing', '2026-06-11 16:45:00+00',
          'Seattle', 'WA', 81.84)
  ON CONFLICT (order_number_norm) DO NOTHING RETURNING order_id
), ins_items AS (
  INSERT INTO commerce.order_items (order_id, part_id, ps_number, name, unit_price_usd, quantity)
  SELECT o.order_id,
         (SELECT part_id FROM catalog.parts WHERE ps_number_norm = catalog.norm_id(p.ps)),
         p.ps, p.nm, p.price, p.qty
  FROM o, (VALUES
    ('PS7784018',  'Refrigerator Water Inlet Valve', 62.60::numeric, 1),
    ('PS11746591', 'Dishwasher Rack Track Stop',      9.62::numeric, 2)
  ) AS p(ps, nm, price, qty)
)
INSERT INTO commerce.order_events (order_id, event_type, occurred_at, description)
SELECT o.order_id, e.event_type, e.occurred_at, e.description
FROM o, (VALUES
  ('placed',     '2026-06-11 16:45:00+00'::timestamptz, 'Order placed'),
  ('processing', '2026-06-11 20:30:00+00'::timestamptz, 'Preparing your order')
) AS e(event_type, occurred_at, description);

-- 4) RETURN_REQUESTED (previously delivered)
WITH o AS (
  INSERT INTO commerce.orders
    (order_number, email, status, placed_at, carrier, tracking_number,
     shipping_city, shipping_region, total_usd)
  VALUES ('LILY-1004', 'demo@lily.test', 'return_requested', '2026-05-20 09:00:00+00',
          'USPS', '9400111899223818000000', 'Portland', 'OR', 84.45)
  ON CONFLICT (order_number_norm) DO NOTHING RETURNING order_id
), ins_items AS (
  INSERT INTO commerce.order_items (order_id, part_id, ps_number, name, unit_price_usd, quantity)
  SELECT o.order_id,
         (SELECT part_id FROM catalog.parts WHERE ps_number_norm = catalog.norm_id('PS11701542')),
         'PS11701542', 'Refrigerator Ice and Water Filter', 84.45, 1
  FROM o
)
INSERT INTO commerce.order_events (order_id, event_type, occurred_at, description)
SELECT o.order_id, e.event_type, e.occurred_at, e.description
FROM o, (VALUES
  ('placed',            '2026-05-20 09:00:00+00'::timestamptz, 'Order placed'),
  ('shipped',           '2026-05-21 11:00:00+00'::timestamptz, 'Shipped via USPS'),
  ('delivered',         '2026-05-24 14:00:00+00'::timestamptz, 'Delivered'),
  ('return_requested',  '2026-05-27 10:15:00+00'::timestamptz, 'Return requested by customer')
) AS e(event_type, occurred_at, description);
