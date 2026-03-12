FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv==0.10.9
# 复制依赖文件
COPY requirements.txt .
# 安装 Python 依赖
RUN uv pip install --system --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建必要的目录
RUN mkdir -p logs data

# 声明挂载的数据卷
VOLUME ["/app/logs", "/app/data"]

# 暴露服务端口
EXPOSE 2321

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 使用 uvicorn 启动 FastAPI 应用（生产环境推荐方式）
CMD ["uvicorn", "main_personal_llm:app", "--host", "0.0.0.0", "--port", "2321", "--workers", "1"]
