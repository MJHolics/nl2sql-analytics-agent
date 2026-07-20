-- 집계 마트(사전집계 테이블, CTAS). 작은 요약 테이블이라 조회 시 스캔이 급감한다.
-- 예: '카테고리별 매출'을 원본에서 풀면 order_items 전체(수백 MB)를 스캔하지만,
--     mart_category_revenue(카테고리 수십 행)는 수 KB만 스캔한다.
-- 자리표시자: {SOURCE}=원본 project.dataset, {MART}=마트 project.dataset

-- 카테고리별 매출
CREATE OR REPLACE TABLE `{MART}.mart_category_revenue` AS
SELECT p.category AS category,
       SUM(oi.sale_price) AS revenue,
       COUNT(*) AS item_count
FROM `{SOURCE}.order_items` oi
JOIN `{SOURCE}.products` p ON oi.product_id = p.id
GROUP BY p.category;

-- 일별 주문/완료주문
CREATE OR REPLACE TABLE `{MART}.mart_daily_orders` AS
SELECT DATE(created_at) AS order_date,
       COUNT(*) AS total_orders,
       COUNTIF(status = 'Complete') AS completed_orders
FROM `{SOURCE}.orders`
GROUP BY order_date;

-- 유입 채널별 고객 수
CREATE OR REPLACE TABLE `{MART}.mart_traffic_customers` AS
SELECT traffic_source,
       COUNT(*) AS customers
FROM `{SOURCE}.users`
GROUP BY traffic_source;
