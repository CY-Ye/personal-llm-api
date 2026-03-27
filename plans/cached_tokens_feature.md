# LLM 缓存 Token 命中信息功能方案

## 1. 需求概述

增加 LLM 缓存 token 命中信息记录，以便更好地计算成本和分析缓存命中率。

## 2. 实现方案

### 2.1 存储字段设计

采用**分开记录价格**方案：
- 保留原有 `input_price`（基于总 prompt_tokens 计算的全价）
- 新增 `cached_tokens`（缓存命中 token 数）
- 新增 `cached_input_price`（基于缓存 token 和模型配置的 cached_unit_price 计算）

### 2.2 数据库变更

#### 2.2.1 模型配置表变更

为 `llm_model` 表添加缓存单价字段：

**MySQL (`db/add_cached_unit_price_field.sql`)**

```sql
-- 添加 cached_unit_price 字段（缓存 token 单价，默认 0 表示不支持缓存）
ALTER TABLE llm_model
ADD COLUMN cached_unit_price FLOAT DEFAULT 0 NULL COMMENT '缓存 token 单价（每千 token）';
```

**SQLite (`db/add_cached_unit_price_field_sqlite.sql`)**

```sql
ALTER TABLE llm_model
ADD COLUMN cached_unit_price FLOAT DEFAULT 0;
```

#### 2.2.2 LLM 使用记录表变更

为 `llm_chat_history` 表添加缓存命中相关字段：

**MySQL (`db/add_cached_tokens_field.sql`)**

```sql
-- 日期：2026-03-27
-- 说明：为 llm_chat_history 表添加 cached_tokens 和 cached_input_price 字段
-- ============================================================

-- 添加 cached_tokens 字段（缓存命中 token 数）
ALTER TABLE llm_chat_history
ADD COLUMN cached_tokens INT DEFAULT 0 NULL COMMENT '缓存命中 token 数';

-- 添加 cached_input_price 字段（缓存部分的输入价格）
ALTER TABLE llm_chat_history
ADD COLUMN cached_input_price FLOAT DEFAULT 0 NULL COMMENT '缓存部分输入价格';
```

**SQLite (`db/add_cached_tokens_field_sqlite.sql`)**

```sql
ALTER TABLE llm_chat_history
ADD COLUMN cached_tokens INT DEFAULT 0;

ALTER TABLE llm_chat_history
ADD COLUMN cached_input_price FLOAT DEFAULT 0;
```

### 2.3 服务层变更

#### 需要修改的文件

| 文件 | 修改内容 |
|------|----------|
| `service/llm_service.py` | 基础类，增加 `cached_tokens` 提取逻辑，使用 `cached_unit_price` 计算价格 |
| `service/open_router_llm.py` | 覆写 `get_usage` 方法，提取缓存 token |
| `service/qwen_llm.py` | 直接复用基类方法（格式一致） |
| `service/byte_llm.py` | 直接复用基类方法（待确认格式） |
| `service/aihubmix_llm.py` | 直接复用基类方法（取决于底层服务商） |
| `service/seedream.py` | 不适用（图像生成无缓存概念） |

#### 缓存 Token 提取逻辑

不同服务商的缓存 token 字段位置：

| 服务商 | 字段位置 | 说明 |
|--------|----------|------|
| OpenAI | `response['usage']['prompt_tokens_details']['cached_tokens']` | 标准字段 |
| OpenRouter | `response['usage']['prompt_tokens_details']['cached_tokens']` | 透传 OpenAI 格式 |
| Qwen | `response['usage']['prompt_tokens_details']['cached_tokens']` | 通义千问支持 |
| Byte | 待确认 | 字节豆包可能支持 |
| Aihubmix | 待确认 | 取决于底层服务商 |
| Seedream | 不适用 | 图像生成服务无缓存概念 |

#### `llm_service.py` 修改

```python
async def get_usage(self, response, params, answer):
    if response['usage']:
        cached_tokens = self._extract_cached_tokens(response['usage'])
        # 使用模型配置的 cached_unit_price 计算缓存价格
        # cached_unit_price 为 0 表示不支持缓存
        cached_input_price = self.cached_unit_price * (cached_tokens / 1000) if cached_tokens > 0 and self.cached_unit_price > 0 else 0
        usage = {
            'completion_tokens': response['usage']['completion_tokens'],
            'prompt_tokens': response['usage']['prompt_tokens'],
            'total_tokens': response['usage']['total_tokens'],
            'cached_tokens': cached_tokens,
            'cached_input_price': cached_input_price
        }
        return usage
    else:
        return {'completion_tokens': 0, 'prompt_tokens': 0, 'total_tokens': 0, 'cached_tokens': 0, 'cached_input_price': 0}

def _extract_cached_tokens(self, usage):
    """提取缓存命中的 token 数"""
    # OpenAI 格式
    if 'prompt_tokens_details' in usage and 'cached_tokens' in usage['prompt_tokens_details']:
        return usage['prompt_tokens_details']['cached_tokens']
    return 0
```

#### `LLMService.__init__` 修改

```python
class LLMService:
    def __init__(self, id, base_url, model_id, api_key, provider_english_name, model_name, input_unit_price, output_unit_price, default_params, cached_unit_price=0):
        # ... 现有代码 ...
        self.cached_unit_price = cached_unit_price  # 新增
```

#### `update_tokens` 方法修改

```python
async def update_tokens(self, history, response, ttft_ms=None):
    # ... 现有代码 ...

    update_data = {}
    if response['usage']:
        update_data['completion_tokens'] = response['usage']['completion_tokens']
        update_data['prompt_tokens'] = response['usage']['prompt_tokens']
        update_data['input_price'] = self.input_unit_price * (response['usage']['prompt_tokens'] / 1000)
        update_data['output_price'] = self.output_unit_price * (response['usage']['completion_tokens'] / 1000)
        # 新增：缓存 token 和缓存部分价格
        update_data['cached_tokens'] = response['usage'].get('cached_tokens', 0)
        update_data['cached_input_price'] = response['usage'].get('cached_input_price', 0)
    # ... 现有代码 ...
```

### 2.4 OpenRouter 特殊处理

`open_router_llm.py` 的 `get_usage` 方法需要修改：

```python
async def get_usage(self, response, params, answer):
    if response['usage']:
        completion_tokens = response['usage']['completion_tokens']

        if self.model_id == 'google/gemini-3-pro-image-preview':
            rate = 120 / 12
            if 'completion_tokens_details' in response['usage'] and 'image_tokens' in response['usage']['completion_tokens_details']:
                image_tokens = response['usage']['completion_tokens_details']['image_tokens']
                completion_tokens += image_tokens * rate

        cached_tokens = self._extract_cached_tokens(response['usage'])
        cached_input_price = self.cached_unit_price * (cached_tokens / 1000) if cached_tokens > 0 and self.cached_unit_price > 0 else 0
        return {
            'completion_tokens': completion_tokens,
            'prompt_tokens': response['usage']['prompt_tokens'],
            'total_tokens': response['usage']['prompt_tokens'] + completion_tokens,
            'cached_tokens': cached_tokens,
            'cached_input_price': cached_input_price
        }
    # ... 其余代码 ...
```

## 3. 实施步骤

### 步骤 1: 创建数据库迁移脚本

- [ ] 创建 `db/add_cached_tokens_field.sql` (MySQL)
- [ ] 创建 `db/add_cached_tokens_field_sqlite.sql` (SQLite)

### 步骤 2: 修改服务层基类

- [ ] 修改 `service/llm_service.py`:
  - 添加 `_extract_cached_tokens` 方法
  - 修改 `get_usage` 方法返回值
  - 修改 `update_tokens` 方法更新 `cached_tokens` 字段

### 步骤 3: 修改各服务商实现类

- [ ] 修改 `service/open_router_llm.py` 的 `get_usage` 方法
- [ ] 检查并修改其他服务商的 `get_usage` 方法（如需要）

### 步骤 4: 更新统计 API

在 `backend/llm_usage.py` 中增加以下接口：

#### 4.1 缓存 Token 统计接口

```python
@router.get("/chart-cached-token")
@require_auth
async def chart_cached_token(request: Request, params: ChartBase = Depends(get_chart_params)):
    """
    获取缓存 Token 命中图表数据
    """
    # 使用与 chart-token 相同的 xAxis 构建逻辑
    # ...
    
    sql = f"""
        SELECT {search_column_name}, 
               SUM(cached_tokens) AS cached_tokens,
               SUM(prompt_tokens) AS prompt_tokens
        FROM llm_chat_history
        {where_sql}
        GROUP BY {search_column_name} order by {search_column_name}
    """
    
    # 计算缓存命中率
    # ...
```

#### 4.2 总使用情况增加缓存 Token 统计

在 `total-usage` 接口的 SQL 中增加：

```sql
SELECT 
    COUNT(1) AS total_request, 
    SUM(prompt_tokens) AS prompt_tokens, 
    SUM(completion_tokens) AS completion_tokens, 
    SUM(input_price) AS input_price, 
    SUM(output_price) AS output_price,
    SUM(cached_tokens) AS cached_tokens  -- 新增
FROM llm_chat_history
{where_sql}
```

### 步骤 5: 更新前端展示

在 `dashboard/pages/llm-usage.json` 中：

#### 5.1 在总览卡片中增加缓存 Token 显示

```json
{
    "type": "card",
    "body": [
        {
            "type": "tpl",
            "tpl": "缓存 Token",
            "className": "font-medium text-gray-500"
        },
        {
            "type": "tpl",
            "tpl": "${cachedTokens | number}",
            "className": "text-2xl font-bold"
        }
    ]
}
```

#### 5.2 增加缓存命中率图表

```json
{
    "type": "chart",
    "api": "get:/backend/llm-usage/chart-cached-token",
    "title": "缓存命中率趋势"
}
```

### 步骤 6: 更新现有图表（如需要）

可以在现有 Token 消耗图表中叠加显示缓存 Token 占比，或单独显示缓存 Token 数量柱状图。

## 4. 向后兼容性

- 所有变更都添加新字段，不修改现有字段
- 如果 API 响应中不包含缓存 token 信息，`cached_tokens` 和 `cached_input_price` 默认为 0
- 成本计算逻辑保持不变

## 5. 成本计算说明

| 字段 | 说明 |
|------|------|
| `input_price` | 基于总 prompt_tokens 计算的全价（不变） |
| `cached_input_price` | 基于缓存 token 和 cached_unit_price 计算 |
| `actual_input_price` | 实际应支付的输入价格 = input_price - cached_input_price |

**节省率计算**：`savings_rate = cached_input_price / input_price * 100%`

## 6. 文件清单

| 操作 | 文件路径 |
|------|----------|
| 新增 | `db/add_cached_unit_price_field.sql` |
| 新增 | `db/add_cached_unit_price_field_sqlite.sql` |
| 新增 | `db/add_cached_tokens_field.sql` |
| 新增 | `db/add_cached_tokens_field_sqlite.sql` |
| 修改 | `service/llm_service.py` |
| 修改 | `service/open_router_llm.py` |
| 跳过 | `service/qwen_llm.py`（复用基类） |
| 跳过 | `service/byte_llm.py`（复用基类） |
| 跳过 | `service/aihubmix_llm.py`（复用基类） |
| 不适用 | `service/seedream.py`（图像生成无缓存） |
| 修改 | `backend/llm_usage.py` |
| 修改 | `dashboard/pages/llm-usage.json` |

## 7. 统计 API 设计

### 7.1 新增/修改接口

| 接口 | 说明 |
|------|------|
| `GET /backend/llm-usage/chart-cached-token` | 获取缓存 Token 命中趋势图表 |
| `GET /backend/llm-usage/total-usage` (修改) | 总使用情况增加 cached_tokens 和 cached_input_price 字段 |
| `GET /backend/llm-usage/chart-money` (修改) | 消费金额图表增加实际输入价格（input_price - cached_input_price） |

### 7.2 缓存 Token 图表响应格式

```json
{
    "status": 0,
    "msg": "",
    "data": {
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["缓存 Token", "总输入 Token", "缓存命中率"]},
        "title": {"text": "缓存 Token 统计", "left": "center"},
        "xAxis": {"type": "category", "data": ["2026-03-21", "2026-03-22", ...]},
        "yAxis": [
            {"type": "value", "name": "Token", "axisLabel": {"formatter": "{value}"}},
            {"type": "value", "name": "命中率", "axisLabel": {"formatter": "{value}%"}}
        ],
        "series": [
            {"name": "缓存 Token", "data": [100, 200, ...], "type": "bar"},
            {"name": "总输入 Token", "data": [1000, 2000, ...], "type": "bar"},
            {"name": "缓存命中率", "data": [10.0, 10.0, ...], "type": "line", "yAxisIndex": 1}
        ]
    }
}
```

### 7.3 总使用情况响应格式

```json
{
    "status": 0,
    "msg": "",
    "data": {
        "total_request": "1000",
        "total_tokens": "500000",
        "total_price": "25.50",
        "cached_tokens": "100000",
        "cached_input_price": "2.50",
        "actual_input_price": "10.00",
        "savings_rate": 19.6
    }
}
```