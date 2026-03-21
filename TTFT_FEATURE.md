# 首字延迟（TTFT）功能实现说明

## 功能概述

在对话历史页面新增"耗时（首字/总）"列，用于展示流式请求的首字延迟和总耗时，帮助用户了解模型响应性能。

**显示格式**:
- **流式请求**: `123ms/23s` (首字延迟 123ms，总耗时 23 秒)
- **非流式请求**: `无/23s` (总耗时 23 秒)

## 技术实现

### 1. 数据库变更

#### MySQL
- **文件**: `db/init_mysql.sql`
- **变更**: 在 `llm_chat_history` 表添加 `ttft_ms` 字段
- **类型**: `INT DEFAULT 0 NULL`
- **注释**: 首字延迟（毫秒），流式请求专用

#### SQLite
- **文件**: `db/init_sqlite.sql`
- **变更**: 同样添加 `ttft_ms` 字段

### 2. 服务层变更

#### service/llm_service.py

**update_tokens 方法**:
```python
async def update_tokens(self, history, response, ttft_ms=None):
    # ... 原有逻辑 ...
    
    # 记录首字延迟（如果是流式请求）
    if ttft_ms is not None and ttft_ms > 0:
        update_data['ttft_ms'] = ttft_ms
```

**chat_stream 方法**:
```python
# 记录首字时间
first_token_time = None
start_time = time.time()

async for line in response.aiter_lines():
    chunk = line.strip()
    # ... 解析 chunk ...
    
    # 记录首字时间（第一次收到内容时）
    if first_token_time is None and (chunk['choices'][0]['delta'].get('content') or 
                                     chunk['choices'][0]['delta'].get('reasoning_content') or 
                                     chunk['choices'][0]['delta'].get('reasoning')):
        first_token_time = time.time()

# 计算首字延迟
ttft_ms = None
if first_token_time:
    ttft_ms = int((first_token_time - start_time) * 1000)

await self.update_tokens(history, response, ttft_ms)
```

### 3. 后端 API 变更

#### backend/chat.py

**chat-history 接口**:
```python
# 处理耗时信息：流式请求显示 "首字/总"，非流式显示 "无/总"
if item['update_time'] and item['create_time']:
    total_duration = str(int((item['update_time'] - item['create_time']).total_seconds())) + 's'
    # 如果有 ttft_ms 字段且大于 0，说明是流式请求
    if item.get('ttft_ms') and item['ttft_ms'] > 0:
        item['duration'] = f"{item['ttft_ms']}ms/{total_duration}"
    else:
        item['duration'] = f"无/{total_duration}"
```

### 4. 前端页面变更

#### dashboard/pages/chat-history.json

```json
{
  "name": "duration",
  "label": "耗时（首字/总）"
}
```

## 迁移指南

### 对于已有数据库

#### MySQL 用户
执行以下 SQL:
```bash
mysql -u your_user -p your_database < db/add_ttft_ms_field.sql
```

或手动执行:
```sql
ALTER TABLE llm_chat_history 
ADD COLUMN ttft_ms INT DEFAULT 0 NULL COMMENT '首字延迟（毫秒），流式请求专用' 
AFTER output_price;
```

#### SQLite 用户
执行以下 SQL:
```bash
sqlite3 db/llm.db < db/add_ttft_ms_field_sqlite.sql
```

或手动执行:
```sql
ALTER TABLE llm_chat_history ADD COLUMN ttft_ms INT DEFAULT 0;
```

## 使用说明

### 1. 首次安装
直接使用最新的初始化脚本即可，无需额外操作。

### 2. 已有数据升级
1. 执行对应的数据库迁移脚本
2. 重启应用
3. 访问后台管理系统查看对话历史

### 3. 数据说明
- **新产生的流式请求**: 自动记录 `ttft_ms` 值
- **历史数据**: `ttft_ms` 为 0 或 NULL，显示为"无/XXs"
- **非流式请求**: 不设置 `ttft_ms`，显示为"无/XXs"

## 性能影响

- **流式请求**: 增加一个时间戳记录（微秒级开销，可忽略）
- **非流式请求**: 无影响
- **存储空间**: 每条记录增加 4 字节（INT 类型）

## 未来优化

1. **统计指标**: 可以在后台首页展示平均首字延迟、P95/P99 延迟等
2. **告警功能**: 当首字延迟超过阈值时发出告警
3. **模型对比**: 对比不同模型的首字延迟性能
4. **OpenTelemetry 集成**: 将 TTFT 指标导出到监控系统

## 相关文件清单

### 修改的文件
- `db/init_mysql.sql` - MySQL 表结构定义
- `db/init_sqlite.sql` - SQLite 表结构定义
- `service/llm_service.py` - LLM 服务基类
- `backend/chat.py` - 对话历史 API
- `dashboard/pages/chat-history.json` - 前端页面配置

### 新增的文件
- `db/add_ttft_ms_field.sql` - MySQL 迁移脚本
- `db/add_ttft_ms_field_sqlite.sql` - SQLite 迁移脚本

## 测试验证

### 1. 发送流式请求
```bash
curl -X POST http://localhost:2321/v1/chat/completions \
  -H "Authorization: Bearer sk-your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-model",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }'
```

### 2. 查看对话历史
访问 `http://localhost:2321/dashboard/#/pages/chat-history`

检查"耗时（首字/总）"列是否显示类似 `123ms/23s` 的格式。

### 3. 数据库验证
```sql
-- 查看最近的记录
SELECT id, model_name, ttft_ms, create_time, update_time 
FROM llm_chat_history 
ORDER BY id DESC 
LIMIT 10;
```

## 注意事项

1. **兼容性**: 历史数据会显示为"无/XXs"，这是正常现象
2. **精度**: TTFT 单位为毫秒，实际精度取决于系统时钟
3. **异常处理**: 如果流式请求未产生任何内容就失败，TTFT 可能为 NULL
4. **多模态**: 图片生成请求也会记录 TTFT（第一个图片块返回时间）

## 相关文档

- [项目架构文档](README.md)
- [数据库设计](db/init_mysql.sql)
- [API 文档](backend/chat.py)
