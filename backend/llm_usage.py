import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator

from utils.util import get_before_timestamp, get_before_month, require_auth, get_current_timestamp, get_before_day, get_current_timestamp, get_before_hour, get_before_minute
from utils.db_client import db_client

router = APIRouter(prefix="/backend/llm-usage", tags=["backend-llm-usage"])


class ChartBase(BaseModel):
    # 不能为空
    before_num: Optional[str]  # 可选字段
    unit_type: Optional[str]  # 可选字段
    model_name: Optional[str] = None  # 新增：模型名称
    provider_name: Optional[str] = None  # 新增：服务商名称
    start_date: Optional[str] = None  # 新增：起始日期
    end_date: Optional[str] = None  # 新增：结束日期
    date_range_type: Optional[str] = 'relative'  # 新增：日期范围类型 relative/absolute

    @field_validator('unit_type')
    def validate_unit_type(cls, v):
        """时间单位格式验证"""
        if not v:
            v = 'day'
        if v not in ['day', 'month', 'year', 'hour', 'minute']:
            raise ValueError('时间单位必须是 day 或 month 或 year 或 hour 或 minute')
        return v

    @field_validator('before_num')
    def validate_before_num(cls, v):
        """时间范围格式验证"""
        if not v:
            v = '7'
        try:
            v = int(v)
        except ValueError:
            raise ValueError('时间范围必须是整数')

        if v <= 0:
            raise ValueError('时间范围必须大于0')
        return v


def get_chart_params(
    before_num: Optional[str] = None,
    unit_type: Optional[str] = None,
    model_name: Optional[str] = None,
    provider_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    return ChartBase(
        before_num=before_num,
        unit_type=unit_type,
        model_name=model_name,
        provider_name=provider_name,
        start_date=start_date,
        end_date=end_date
    )


def build_where_conditions(params: ChartBase) -> tuple[str, str]:
    """
    根据参数动态构建 WHERE 条件和日期范围
    :param params: ChartBase 参数对象
    :return: (where_sql, date_str_for_chart) where_sql 是完整的 WHERE 子句，date_str_for_chart 是图表需要的时间起始点
    """
    where_clauses = []
    date_str = None
    
    # 检查是否使用日期范围模式：只要有 start_date 就进入日期范围模式
    has_start_date = params.start_date and params.start_date.strip()
    
    if has_start_date:
        # 日期范围模式
        # 如果 end_date 为空，则使用当前日期作为结束日期
        end_date = params.end_date if (params.end_date and params.end_date.strip()) else datetime.datetime.now().strftime('%Y-%m-%d')
        
        where_clauses.append(f"create_time >= '{params.start_date} 00:00:00'")
        where_clauses.append(f"create_time <= '{end_date} 23:59:59'")
    else:
        # 相对时间模式（默认）
        before_num = int(params.before_num) if params.before_num else 7
        if params.unit_type == 'day':
            date_str = get_before_day(before_num - 1) + ' 00:00:00'
        elif params.unit_type == 'month':
            date_str = get_before_month(before_num - 1) + ' 00:00:00'
        elif params.unit_type == 'year':
            current_year = get_current_timestamp()[:4]
            date_str = f'{int(current_year) - before_num + 1}-01-01 00:00:00'
        elif params.unit_type == 'hour':
            date_str = get_before_hour(before_num - 1).replace(' ', ' ') + ':00:00'
        elif params.unit_type == 'minute':
            date_str = get_before_minute(before_num - 1).replace(' ', ' ') + ':00'
        
        if date_str:
            where_clauses.append(f"create_time >= '{date_str}'")
    
    # 模型筛选
    if params.model_name and params.model_name.strip():
        where_clauses.append(f"model_name = '{params.model_name}'")
    
    # 服务商筛选
    if params.provider_name and params.provider_name.strip():
        where_clauses.append(f"provider_name = '{params.provider_name}'")
    
    if where_clauses:
        return "WHERE " + " AND ".join(where_clauses), date_str
    return "", date_str


async def get_xAxis_from_db(search_column_name: str, where_sql: str):
    """从数据库获取实际的日期列表"""
    date_sql = f"""
        SELECT DISTINCT {search_column_name}
        FROM llm_chat_history
        {where_sql}
        ORDER BY {search_column_name}
    """
    date_res = await db_client.select(date_sql)
    return [item[search_column_name] for item in date_res]

def get_day_params(params):
    xAxis = []
    yAxis = []

    format_str = '%Y-%m-%d'
    for i in range(params.before_num - 1, -1, -1):
        time_stamp = get_before_timestamp(i)
        # 格式化 time_stamp 时间戳
        xAxis.append(datetime.datetime.fromtimestamp(time_stamp).strftime(format_str))
        yAxis.append(0)
    date_str = get_before_day(params.before_num - 1) + ' 00:00:00'
    search_column_name = 'create_day'

    return xAxis, yAxis, date_str, search_column_name

def get_hour_params(params):
    """获取小时级别的图表参数"""
    xAxis = []
    yAxis = []
    
    format_str = '%Y-%m-%d %H'
    for i in range(params.before_num - 1, -1, -1):
        hour_str = get_before_hour(i)
        xAxis.append(hour_str)
        yAxis.append(0)
    
    date_str = get_before_hour(params.before_num - 1) + ':00:00'
    search_column_name = 'create_hour'
    
    return xAxis, yAxis, date_str, search_column_name

def get_minute_params(params):
    """获取分钟级别的图表参数"""
    xAxis = []
    yAxis = []
    
    format_str = '%Y-%m-%d %H:%M'
    for i in range(params.before_num - 1, -1, -1):
        minute_str = get_before_minute(i)
        xAxis.append(minute_str)
        yAxis.append(0)
    
    date_str = get_before_minute(params.before_num - 1) + ':00'
    search_column_name = 'create_minute'
    
    return xAxis, yAxis, date_str, search_column_name

def get_month_params(params):
    xAxis = []
    yAxis = []
    format_str = '%Y-%m'
    for i in range(params.before_num - 1, -1, -1):
        month_str = get_before_month(i)

        xAxis.append(month_str[:7])
        yAxis.append(0)
    date_str = get_before_month(params.before_num - 1) + ' 00:00:00'
    search_column_name = 'create_month'

    return xAxis, yAxis, date_str, search_column_name

def get_year_params(params):
    xAxis = []
    yAxis = []
    for i in range(params.before_num - 1, -1, -1):
        current_year = get_current_timestamp()[:4]

        xAxis.append(str(int(current_year) - i))
        yAxis.append(0)
    current_year = get_current_timestamp()[:4]
    date_str = f'{int(current_year) - params.before_num + 1}-01-01 00:00:00'
    search_column_name = 'create_year'

    return xAxis, yAxis, date_str, search_column_name

# 获取请求次数图表数据
@router.get("/chart-request")
@require_auth
async def chart_request(request: Request, params: ChartBase = Depends(get_chart_params)):

    xAxis = []
    yAxis = []

    # 如果使用了日期范围筛选（只要有 start_date 就进入日期范围模式）
    has_start_date = params.start_date and params.start_date.strip()
    
    if has_start_date:
        search_column_name = 'create_day'
        where_sql, _ = build_where_conditions(params)
        
        # 先查询所有存在的日期
        date_sql = f"""
            SELECT DISTINCT {search_column_name}
            FROM llm_chat_history
            {where_sql}
            ORDER BY {search_column_name}
        """
        date_res = await db_client.select(date_sql)
        xAxis = [item[search_column_name] for item in date_res]
        yAxis = [0] * len(xAxis)
    else:
        # 使用原有的 before_num 逻辑
        if params.unit_type == 'day':
            xAxis, yAxis, _, search_column_name = get_day_params(params)

        elif params.unit_type == 'month':
            xAxis, yAxis, _, search_column_name = get_month_params(params)

        elif params.unit_type == 'year':
            xAxis, yAxis, _, search_column_name = get_year_params(params)
        
        elif params.unit_type == 'hour':
            xAxis, yAxis, _, search_column_name = get_hour_params(params)
        
        elif params.unit_type == 'minute':
            xAxis, yAxis, _, search_column_name = get_minute_params(params)

    # 使用动态 WHERE 条件
    where_sql, _ = build_where_conditions(params)

    sql = f"""
        SELECT {search_column_name}, COUNT(*) AS count
        FROM llm_chat_history
        {where_sql}
        GROUP BY {search_column_name} order by {search_column_name}
    """

    res = await db_client.select(sql)
    res_dict = {item[search_column_name]: item['count'] for item in res}

    # 填充数据
    for i, date_name in enumerate(xAxis):
        if date_name in res_dict:
            yAxis[i] = res_dict[date_name]

    data = {
        "tooltip": {
            "trigger": 'axis'
        },
        "title": {
            "text": '请求次数',
            "left": 'center',
            "bottom": '0%',
            "textStyle": {
                "fontSize": 14,
                "color": '#666'
            }
        },
        "xAxis": {
            "type": 'category',
            "data": xAxis
        },
        "yAxis": {
            "type": 'value',
            "axisLabel": {
                "formatter": '{value} 次'
            }
        },
        "series": [
            {
                "data": yAxis,
                "type": 'line',
                "smooth": True
            }
        ]
    }

    data = {'status': 0, 'msg': '', 'data': data}
    return data

# 获取 token 使用图表数据
@router.get("/chart-token")
@require_auth
async def chart_token(request: Request, params: ChartBase = Depends(get_chart_params)):

    xAxis = []
    yAxis_prompt = []
    yAxis_completion = []

    # 如果使用了日期范围筛选（只要有 start_date 就进入日期范围模式）
    has_start_date = params.start_date and params.start_date.strip()
    
    if has_start_date:
        search_column_name = 'create_day'
        where_sql, _ = build_where_conditions(params)
        
        # 先查询所有存在的日期
        date_sql = f"""
            SELECT DISTINCT {search_column_name}
            FROM llm_chat_history
            {where_sql}
            ORDER BY {search_column_name}
        """
        date_res = await db_client.select(date_sql)
        xAxis = [item[search_column_name] for item in date_res]
        yAxis_prompt = [0] * len(xAxis)
        yAxis_completion = [0] * len(xAxis)
    else:
        # 使用原有的 before_num 逻辑
        if params.unit_type == 'day':
            format_str = '%Y-%m-%d'
            for i in range(params.before_num - 1, -1, -1):
                time_stamp = get_before_timestamp(i)
                # 格式化 time_stamp 时间戳
                xAxis.append(datetime.datetime.fromtimestamp(time_stamp).strftime(format_str))
                yAxis_prompt.append(0)
                yAxis_completion.append(0)
            date_str = get_before_day(int(params.before_num) - 1) + ' 00:00:00'
            search_column_name = 'create_day'

        elif params.unit_type == 'month':
            format_str = '%Y-%m'
            for i in range(params.before_num - 1, -1, -1):
                month_str = get_before_month(i)

                xAxis.append(month_str)
                yAxis_prompt.append(0)
                yAxis_completion.append(0)
            date_str = get_before_month(params.before_num - 1) + ' 00:00:00'
            search_column_name = 'create_month'

        elif params.unit_type == 'year':
            for i in range(params.before_num - 1, -1, -1):
                current_year = get_current_timestamp()[:4]

                xAxis.append(str(int(current_year) - i))
                yAxis_prompt.append(0)
                yAxis_completion.append(0)
            search_column_name = 'create_year'
        
        elif params.unit_type == 'hour':
            xAxis, yAxis_prompt, _, search_column_name = get_hour_params(params)
            yAxis_completion = [0] * len(xAxis)
        
        elif params.unit_type == 'minute':
            xAxis, yAxis_prompt, _, search_column_name = get_minute_params(params)
            yAxis_completion = [0] * len(xAxis)
    # 使用动态 WHERE 条件
    where_sql, _ = build_where_conditions(params)

    sql = f"""
        SELECT {search_column_name}, SUM(prompt_tokens) AS prompt_tokens, SUM(completion_tokens) AS completion_tokens
        FROM llm_chat_history
        {where_sql}
        GROUP BY {search_column_name} order by {search_column_name}
    """

    res = await db_client.select(sql)
    res = {item[search_column_name]: {'prompt_tokens': item['prompt_tokens'], 'completion_tokens': item['completion_tokens']} for item in res}

    for i, name in enumerate(xAxis):
        if name in res:
            yAxis_prompt[i] = res[name]['prompt_tokens']
            yAxis_completion[i] = res[name]['completion_tokens']

    data = {
        "tooltip": {
            "trigger": 'axis'
        },
        "legend": {
            "data": ['输入 Token', '输出 Token']
        },
        "title": {
            "text": 'Token 消耗',
            "left": 'center',
            "bottom": '0%',
            "textStyle": {
                "fontSize": 14,
                "color": '#666'
            }
        },
        "xAxis": {
            "type": 'category',
            "data": xAxis
        },
        "yAxis": {
            "type": 'value',
            "axisLabel": {
                "formatter": '{value} token'
            }
        },
        "series": [
            {
                "name": '输入 Token',
                "data": yAxis_prompt,
                "type": 'line',
                "smooth": True
            },
            {
                "name": '输出 Token',
                "data": yAxis_completion,
                "type": 'line',
                "smooth": True
            }
        ]
    }

    data = {'status': 0, 'msg': '', 'data': data}
    return data

# 获取消费金额图表数据
@router.get("/chart-money")
@require_auth
async def chart_money(request: Request, params: ChartBase = Depends(get_chart_params)):

    xAxis = []
    yAxis = []

    # 如果使用了日期范围筛选（只要有 start_date 就进入日期范围模式）
    has_start_date = params.start_date and params.start_date.strip()
    
    if has_start_date:
        search_column_name = 'create_day'
        where_sql, _ = build_where_conditions(params)
        
        # 先查询所有存在的日期
        date_sql = f"""
            SELECT DISTINCT {search_column_name}
            FROM llm_chat_history
            {where_sql}
            ORDER BY {search_column_name}
        """
        date_res = await db_client.select(date_sql)
        xAxis = [item[search_column_name] for item in date_res]
        yAxis = [0] * len(xAxis)
    else:
        # 使用原有的 before_num 逻辑
        if params.unit_type == 'day':
            xAxis, yAxis, _, search_column_name = get_day_params(params)

        elif params.unit_type == 'month':
            xAxis, yAxis, _, search_column_name = get_month_params(params)

        else:
            xAxis, yAxis, _, search_column_name = get_year_params(params)

    # 使用动态 WHERE 条件
    where_sql, _ = build_where_conditions(params)

    sql = f"""
        SELECT {search_column_name}, SUM(input_price) AS input_price, SUM(output_price) AS output_price
        FROM llm_chat_history
        {where_sql}
        GROUP BY {search_column_name} order by {search_column_name}
    """

    res = await db_client.select(sql)
    res = {item[search_column_name]: {'price': item['input_price'] + item['output_price']} for item in res}

    for i, name in enumerate(xAxis):
        if name in res:
            yAxis[i] = f"{res[name]['price']:.6g}"

    data = {
        "tooltip": {
            "trigger": 'axis'
        },
        "title": {
            "text": '消费金额',
            "left": 'center',
            "bottom": '0%',
            "textStyle": {
                "fontSize": 14,
                "color": '#666'
            }
        },
        "xAxis": {
            "type": 'category',
            "data": xAxis
        },
        "yAxis": {
            "type": 'value',
            "axisLabel": {
                "formatter": '{value} 元'
            }
        },
        "series": [
            {
                "data": yAxis,
                "type": 'line',
                "smooth": True
            }
        ]
    }

    data = {'status': 0, 'msg': '', 'data': data}
    return data


# 获取总使用情况
@router.get("/total-usage")
@require_auth
async def total_usage(
    request: Request,
    model_name: Optional[str] = None,
    provider_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    before_num: Optional[str] = None,
    unit_type: Optional[str] = None
):
    # 构建筛选条件
    params = ChartBase(
        model_name=model_name,
        provider_name=provider_name,
        start_date=start_date,
        end_date=end_date,
        before_num=before_num,
        unit_type=unit_type
    )
    where_sql, _ = build_where_conditions(params)
    
    # 添加 update_time 条件
    if where_sql:
        where_sql += " AND update_time is not null"
    else:
        where_sql = "WHERE update_time is not null"
    
    sql = f"""
        SELECT COUNT(1) AS total_request, SUM(prompt_tokens) AS prompt_tokens, SUM(completion_tokens) AS completion_tokens, SUM(input_price) AS input_price, SUM(output_price) AS output_price
        FROM llm_chat_history
        {where_sql}
    """

    res = await db_client.select(sql)
    res = res[0]

    if res['total_request'] != 0:
        total_price = str(round(res['input_price'] + res['output_price'], 2))
        if total_price == '0.0':
            total_price = str(round(res['input_price'] + res['output_price'], 6))

        data = {
            'total_request': str(res['total_request']),
            'total_tokens': str(res['prompt_tokens'] + res['completion_tokens']),
            'total_price': total_price
        }

    else:
        data = {
            'total_request': '0',
            'total_tokens': '0',
            'total_price': '0.00'
        }

    data = {'status': 0, 'msg': '', 'data': data}
    return data
