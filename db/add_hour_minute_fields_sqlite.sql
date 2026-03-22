-- 添加小时和分钟维度统计字段
-- 适用于 SQLite

-- SQLite 不支持直接添加多个列，需要逐条执行
ALTER TABLE llm_chat_history ADD COLUMN create_hour VARCHAR(13) NULL;
ALTER TABLE llm_chat_history ADD COLUMN create_minute VARCHAR(16) NULL;

-- SQLite 索引创建
CREATE INDEX IF NOT EXISTS idx_create_hour ON llm_chat_history(create_hour);
CREATE INDEX IF NOT EXISTS idx_create_minute ON llm_chat_history(create_minute);
