-- 스테이징(의미 계층). 원본 공개셋 위에 뷰로만 만든다 → 저장 비용 0.
-- 업무 용어로 핵심 컬럼만 노출해 "분석가의 말 ↔ 스키마"의 간극을 줄인다.
-- 자리표시자: {SOURCE}=원본 project.dataset, {MART}=마트 project.dataset

CREATE SCHEMA IF NOT EXISTS `{MART}`
  OPTIONS (description = 'NL2SQL 분석 에이전트용 데이터 마트(staging 뷰 + 집계 테이블)');

CREATE OR REPLACE VIEW `{MART}.stg_order_items` AS
SELECT order_id, product_id, sale_price, status, created_at
FROM `{SOURCE}.order_items`;

CREATE OR REPLACE VIEW `{MART}.stg_products` AS
SELECT id AS product_id, category, department, retail_price, brand
FROM `{SOURCE}.products`;

CREATE OR REPLACE VIEW `{MART}.stg_users` AS
SELECT id AS user_id, traffic_source, age, country, gender
FROM `{SOURCE}.users`;

CREATE OR REPLACE VIEW `{MART}.stg_orders` AS
SELECT order_id, user_id, status, created_at, num_of_item
FROM `{SOURCE}.orders`;
