-- ============================================================
-- 数据库迁移脚本：添加首字延迟字段
-- 版本：v1.0
-- 日期：2026-03-21
-- 说明：为 llm_chat_history 表添加 ttft_ms 字段，用于记录流式请求的首字延迟
-- ============================================================

-- 添加 ttft_ms 字段（首字延迟，单位毫秒）
ALTER TABLE llm_chat_history 
ADD COLUMN ttft_ms INT DEFAULT 0 NULL COMMENT '首字延迟（毫秒），流式请求专用' 
AFTER output_price;

-- 验证是否添加成功（可选执行）
-- SELECT column_name, data_type, column_comment, column_default
-- FROM information_schema.columns 
-- WHERE table_schema = DATABASE() 
--   AND table_name = 'llm_chat_history' 
--   AND column_name = 'ttft_ms';
