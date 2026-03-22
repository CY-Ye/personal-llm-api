import datetime
import time
import threading
import os
import base64
import hashlib
from functools import wraps

import pytz
from pydantic import BaseModel, validator
from fastapi import Request
from fastapi.exceptions import HTTPException
from json_repair import json_repair
from PIL import Image
# import sys
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings



# 设置时区
shanghai_tz = pytz.timezone('Asia/Shanghai')

def get_current_timestamp():
    """
    返回当前时间戳，精确到3位毫秒
    :return:
    """
    now = datetime.datetime.now(shanghai_tz)
    timestamp = now.strftime('%Y-%m-%d %H:%M:%S.%f')
    return timestamp[:-3]

def get_before_timestamp(days):
    # 获取当前日期
    now = datetime.datetime.now()
    # 获取今天的0点时间
    today_start = datetime.datetime(now.year, now.month, now.day)
    # 计算指定天数前的0点时间
    before_time = int((today_start - datetime.timedelta(days=int(days))).timestamp())
    return before_time

def get_before_day(days):
    # 获取当前日期
    now = datetime.datetime.now()
    # 获取今天的0点时间
    today_start = datetime.datetime(now.year, now.month, now.day)
    # 计算指定天数前的0点时间
    before_time = today_start - datetime.timedelta(days=int(days))
    return before_time.strftime('%Y-%m-%d')

def get_before_month(months):
    # 获取当前日期
    now = datetime.datetime.now()
    year = now.year
    month = now.month
    for i in range(months, 0, -1):
        month -= 1
        if month <= 0:
            month = 12
            year -= 1
    # 获取指定月份的第一天
    first_day = datetime.datetime(year, month, 1)
    # 计算指定月份的 0 点时间
    return first_day.strftime('%Y-%m-%d')

def get_before_hour(hours):
    """
    获取指定小时前的小时时间字符串（格式：YYYY-MM-DD HH）
    :param hours: 多少小时前
    :return: 格式化的小时字符串
    """
    now = datetime.datetime.now()
    before_time = now - datetime.timedelta(hours=int(hours))
    return before_time.strftime('%Y-%m-%d %H')

def get_before_minute(minutes):
    """
    获取指定分钟前的分钟时间字符串（格式：YYYY-MM-DD HH:MM）
    :param minutes: 多少分钟前
    :return: 格式化的分钟字符串
    """
    now = datetime.datetime.now()
    before_time = now - datetime.timedelta(minutes=int(minutes))
    return before_time.strftime('%Y-%m-%d %H:%M')

def md5_encrypt(string: str) -> str:
    """
    对字符串进行MD5加密
    :param string: 要加密的字符串
    :return: MD5加密后的字符串(32位小写)
    """
    md5_hash = hashlib.md5()
    md5_hash.update(string.encode('utf-8'))
    return md5_hash.hexdigest()

class SnowflakeGenerator:
    def __init__(self, worker_id=0, datacenter_id=0):
        self.worker_id = worker_id
        self.datacenter_id = datacenter_id
        self.sequence = 0
        self.last_timestamp = -1
        self.lock = threading.Lock()

        # 2020-01-01 00:00:00 作为起始时间戳
        self.twepoch = 1577836800000  

    def _current_time(self):
        return int(time.time() * 1000)

    def _wait_next_millis(self, last_timestamp):
        timestamp = self._current_time()
        while timestamp <= last_timestamp:
            timestamp = self._current_time()
        return timestamp

    def next_id(self):
        with self.lock:
            timestamp = self._current_time()

            if timestamp < self.last_timestamp:
                raise Exception("时钟回拨异常")

            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & 0xFFF
                if self.sequence == 0:
                    timestamp = self._wait_next_millis(self.last_timestamp)
            else:
                self.sequence = 0

            self.last_timestamp = timestamp

            return ((timestamp - self.twepoch) << 22) | \
                   (self.datacenter_id << 17) | \
                   (self.worker_id << 12) | \
                   self.sequence

# 全局雪花ID生成器实例
snowflake = SnowflakeGenerator()



# 获取request参数
async def get_request_params(request: Request) -> dict:
    if request.method == 'POST':
        params = await request.json()
    else:
        params = request.query_params._dict
    
    return params

# 验证是否登录
def require_auth(func):
    """自定义装饰器"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # 获取请求对象
        request = kwargs.get('request')
        session = request.session
        # 检查是否登录
        if 'user_id' not in session:
            # 未登录，返回登录页面
            raise HTTPException(status_code=401, detail="Not authenticated")

        return await func(*args, **kwargs)

    return wrapper

# 验证分页参数
class PaginationParams(BaseModel):
    page: int = 1
    perPage: int = 10

    @validator('page')
    def validate_page(cls, v):
        """分页参数验证"""
        if v <= 0:
            raise ValueError('分页参数page必须大于0')
        return v

    @validator('perPage')
    def validate_perPage(cls, v):
        """分页参数验证"""
        if v <= 0:
            raise ValueError('分页参数page_size必须大于0')
        return v

def get_page_params(page: int, perPage: int):
    return PaginationParams(page=page, perPage=perPage)

# base64图片保存
def save_base64_image(base64_str: str):
    # 移除Data URI前缀（如果存在）
    if base64_str.startswith('data:'):
        # 找到base64,开始的位置
        base64_str = base64_str.split('base64,')[-1]
    image_data = base64.b64decode(base64_str)

    current = get_current_timestamp()[0:-4]
    year = current[0:4]
    month = current[5:7]
    day = current[8:10]
    image_path = os.path.join(settings.PROJECT_PATH, 'static/images/chat', year, month, day)
    if not os.path.exists(image_path):
        os.makedirs(image_path)

    file_name = f'{snowflake.next_id()}.png'
    with open(os.path.join(image_path, file_name), 'wb') as f:
        f.write(image_data)
    file_path = f'/static/images/chat/{year}/{month}/{day}/{file_name}'

    return file_path

def resize_img_limit(width, height, limit=4096):
    """
    计算缩放后的宽高，保持宽高比，且长边不超过 limit (4096)。

    :param width: 原始宽度
    :param height: 原始高度
    :param limit: 限制的最大像素值（默认为 4096）
    :return: (new_width, new_height)
    """
    # 避免除以零
    if width <= 0 or height <= 0:
        return 0, 0
    # 计算宽和高的缩放比例
    # 选取两者中较小的比例，以确保两边都不超过 limit
    scale = min(limit / width, limit / height)
    # 计算新的宽高
    # 使用 round 取整，也可以使用 math.floor (向下取整) 确保绝对不超过 4096
    new_width = int(round(width * scale))
    new_height = int(round(height * scale))

    # 额外保险：由于浮点数精度问题，再次确保不超限
    new_width = min(new_width, limit)
    new_height = min(new_height, limit)
    return new_width, new_height


def get_resolution(k_label, aspect_ratio="16:9"):
    """
    根据通用分辨率标签和宽高比计算具体的宽高

    :param k_label: str, 如 '1k', '2k', '3k', '4k', '8k'
    :param aspect_ratio: str, 如 '16:9', '4:3', '21:9', '1:1'
    :return: tuple, (width, height)
    """
    # 1. 定义 K 级别对应的基准宽度 (基于 DCI 标准)
    k_base_widths = {
        "1k": 1024,
        "2k": 2048,
        "3k": 3072,
        "4k": 4096,
        "8k": 8192
    }

    # 也可以根据习惯调整为消费级标准 (如 2k=1920, 4k=3840)
    # k_base_widths = {"1k": 1280, "2k": 1920, "3k": 3200, "4k": 3840}
    label = k_label.lower()
    if label not in k_base_widths:
        raise ValueError(f"不支持的分辨率标签: {k_label}。请使用 1k, 2k, 3k, 4k 等。")
    # 2. 解析宽高比
    try:
        rw, rh = map(float, aspect_ratio.split(':'))
    except ValueError:
        raise ValueError("宽高比格式错误，应为 '16:9' 这种格式。")
    # 3. 计算宽度和高度
    # 以宽度为基准计算高度
    target_width = k_base_widths[label]
    target_height = (target_width * rh) / rw

    # 4. 格式化输出：通常分辨率需要是偶数 (为了兼容视频编码器如 H.264)
    final_w = int(target_width)
    final_h = int(round(target_height / 2) * 2)

    return final_w, final_h

def read_base64_img_size(base64_str: str):
    file_path = save_base64_image(base64_str)[1:]
    with Image.open(os.path.join(settings.PROJECT_PATH, file_path)) as img:
        width, height = img.size
    return width, height

# 从query提取图片参数
async def extract_img_params(query):
    """从query提取图片参数"""
    prompt =f"""
query如下：
'''
{query}
'''

请从query中提取图片参数，并以json形式返回：
    - resolution_ratio：图片分辨率，例如1k，2k，4k等，默认2k
    - is_use_original_img_rate：布尔类型，是否使用原始图片比例，默认False
    - rate：生成的图片宽高比，默认1:1，如果是已经使用了原图比例，则输出空字符串
    """

    params = {
        'messages': [
            {'role': 'user', 'content': prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
        'api_key_id': 1,
        # "enable_thinking": True,
    }

    # 调用免费模型提取图片参数
    response = await settings.FREE_MODEL.chat(params)
    # 解析json字符串
    img_params = json_repair.loads(response['choices'][0]['message']['content'])

    if img_params['resolution_ratio'] not in ['1k', '2k', '3k', '4k']:
        raise HTTPException(status_code=400, detail="分辨率")

    return img_params
