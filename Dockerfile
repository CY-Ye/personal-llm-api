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

# 启动命令
CMD ["python3", "main_personal_llm.py"]
