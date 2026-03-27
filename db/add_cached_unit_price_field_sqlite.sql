-- 日期：2026-03-27
-- 说明：为 llm_model 表添加 cached_unit_price 字段，用于配置缓存 token 的输入单价
-- ============================================================

-- SQLite 添加字段语法
ALTER TABLE llm_model
ADD COLUMN cached_unit_price FLOAT DEFAULT 0;