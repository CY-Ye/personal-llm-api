-- 日期：2026-03-27
-- 说明：为 llm_chat_history 表添加 cached_tokens 和 cached_price 字段，用于记录缓存命中信息
-- ============================================================

-- MySQL 添加字段语法
ALTER TABLE llm_chat_history
ADD COLUMN cached_tokens INT DEFAULT 0 NULL COMMENT '缓存命中 token 数';

ALTER TABLE llm_chat_history
ADD COLUMN cached_price FLOAT DEFAULT 0 NULL COMMENT '缓存节省的价格';

-- 验证是否添加成功（可选执行）
-- SELECT column_name, data_type, column_comment
-- FROM information_schema.columns
-- WHERE table_schema = DATABASE()
--   AND table_name = 'llm_chat_history'
--   AND column_name IN ('cached_tokens', 'cached_price');