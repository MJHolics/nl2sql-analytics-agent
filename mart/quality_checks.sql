-- 마트 품질 점검. 각 행은 (점검명, 위반 건수). 모든 violations=0 이면 통과.
-- 키 컬럼 NULL·음수 매출·빈 테이블 같은 기본 무결성을 본다(데이터 마트 운영의 품질관리).
-- 자리표시자: {MART}=마트 project.dataset

SELECT 'mart_category_revenue: category NULL' AS check_name,
       COUNTIF(category IS NULL) AS violations
FROM `{MART}.mart_category_revenue`
UNION ALL
SELECT 'mart_category_revenue: revenue 음수',
       COUNTIF(revenue < 0)
FROM `{MART}.mart_category_revenue`
UNION ALL
SELECT 'mart_category_revenue: 빈 테이블',
       CAST(COUNT(*) = 0 AS INT64)
FROM `{MART}.mart_category_revenue`
UNION ALL
SELECT 'mart_daily_orders: 완료>전체(모순)',
       COUNTIF(completed_orders > total_orders)
FROM `{MART}.mart_daily_orders`
UNION ALL
SELECT 'mart_daily_orders: 빈 테이블',
       CAST(COUNT(*) = 0 AS INT64)
FROM `{MART}.mart_daily_orders`
UNION ALL
SELECT 'mart_traffic_customers: traffic_source NULL',
       COUNTIF(traffic_source IS NULL)
FROM `{MART}.mart_traffic_customers`;
