-- ============================================================
-- 数据库迁移脚本：添加首字延迟字段（SQLite 版本）
-- 版本：v1.0
-- 日期：2026-03-21
-- 说明：为 llm_chat_history 表添加 ttft_ms 字段，用于记录流式请求的首字延迟
-- ============================================================

-- SQLite 添加字段语法
ALTER TABLE llm_chat_history 
ADD COLUMN ttft_ms INT DEFAULT 0;

-- 验证是否添加成功（可选执行）
-- PRAGMA table_info(llm_chat_history);
