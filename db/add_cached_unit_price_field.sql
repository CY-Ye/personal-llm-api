-- 日期：2026-03-27
-- 说明：为 llm_model 表添加 cached_unit_price 字段，用于配置缓存 token 的输入单价
-- ============================================================

-- MySQL 添加字段语法
ALTER TABLE llm_model
ADD COLUMN cached_unit_price FLOAT DEFAULT 0 NULL COMMENT '缓存 token 输入单价（每千 token）';

-- 验证是否添加成功（可选执行）
-- SELECT column_name, data_type, column_comment
-- FROM information_schema.columns
-- WHERE table_schema = DATABASE()
--   AND table_name = 'llm_model'
--   AND column_name = 'cached_unit_price';