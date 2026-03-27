-- 日期：2026-03-27
-- 说明：为 llm_chat_history 表添加 cached_tokens 和 cached_price 字段，用于记录缓存命中信息
-- ============================================================

-- SQLite 添加字段语法
ALTER TABLE llm_chat_history
ADD COLUMN cached_tokens INT DEFAULT 0;

ALTER TABLE llm_chat_history
ADD COLUMN cached_price FLOAT DEFAULT 0;