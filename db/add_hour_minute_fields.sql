-- 添加小时和分钟维度统计字段
-- 适用于 MySQL
ALTER TABLE llm_chat_history
ADD COLUMN create_hour VARCHAR(13) NULL COMMENT '小时维度统计字段 YYYY-MM-DD HH' AFTER create_day,
ADD COLUMN create_minute VARCHAR(16) NULL COMMENT '分钟维度统计字段 YYYY-MM-DD HH:MM' AFTER create_hour;

-- 添加索引提升查询性能
CREATE INDEX idx_create_hour ON llm_chat_history(create_hour);
CREATE INDEX idx_create_minute ON llm_chat_history(create_minute);
