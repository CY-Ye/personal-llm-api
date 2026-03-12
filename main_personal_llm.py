import os
import asyncio
import json
import traceback
import base64

from loguru import logger
current_file_path = os.path.abspath(__file__)
log_file = os.path.join(os.path.dirname(current_file_path), 'logs', 'personal_llm_{time:YYYY-MM-DD}.log')
logger.add(
    log_file,  # 按日期命名的日志文件
    rotation="00:00",              # 每天午夜轮转
    retention="10 days",           # 保留10天的日志
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} - {message}",
    level="INFO"
)


# 导入 FastAPI
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse
from pydantic_core import ValidationError

from init import init_db, init_models, get_model, MODELS_OBJ
from config import settings
from utils.db_client import db_client
from backend.backend_api import backend_router
from backend.llm_usage import router as llm_usage_router
from backend.api_manage import router as api_router
from backend.chat import router as chat_router


async def init_app():
    # 初始化数据库
    await init_db()
    # 初始化模型
    await init_models()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期管理器"""
    # Startup
    logger.info("Starting up: Initializing database and models...")
    await init_app()
    logger.info("Startup complete!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down: Cleaning up resources...")
    # 在这里添加清理逻辑，例如关闭数据库连接等


# 创建 FastAPI 应用实例
app = FastAPI(
    docs_url=None,      # 禁用 Swagger UI
    redoc_url=None,     # 禁用 ReDoc
    openapi_url=None,   # 禁用 OpenAPI JSON
    lifespan=lifespan   # 使用 lifespan 管理生命周期
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境不要用 *
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key='personal-llm-123',
    # 可选参数
    session_cookie="session",
    max_age=60*60*24,  # 1小时
    same_site="lax",
    https_only=False  # 开发环境设为False，生产环境建议设为True
)

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static/"), name="static1")

# 挂载后端路由
app.include_router(backend_router)
app.include_router(llm_usage_router)
app.include_router(api_router)
app.include_router(chat_router)



@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """自定义验证错误处理器"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error['loc']),
            "message": str(error['ctx']['error']) if 'ctx' in error else '',
            "type": error['type']
        })

    return JSONResponse(
        status_code=200,
        content={"status": 1, "msg": errors[0]['message']}
    )

@app.exception_handler(ValidationError)
async def validation_exception_handler2(request, exc):
    """自定义验证错误处理器"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error['loc']),
            "message": str(error['ctx']['error']) if 'ctx' in error else '',
            "type": error['type']
        })

    return JSONResponse(
        status_code=200,
        content={"status": 1, "msg": errors[0]['message']}
    )


async def chat_stream(model, params):

    try:
        # 判断是否使用response接口
        is_use_response_interface = False
        for item in params.get('tools', []):
            if item['type'] == 'web_search':
                is_use_response_interface = True
                break

        if is_use_response_interface:
            async for chunk in model.chat_stream_response(params):
                ## sse返回数据
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        else:
            async for chunk in model.chat_stream(params):
                ## sse返回数据
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        # 完成
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(traceback.format_exc())


# 校验api key是否存在
async def check_api_key(api_key: str):
    """校验api key是否存在"""
    if not api_key:
        raise HTTPException(status_code=401, detail='api key error!')

    api_key = api_key.replace('Bearer ', '')
    if not api_key or not api_key.startswith('sk-'):
        raise HTTPException(status_code=401, detail='api key error!')

    sql = f"SELECT api_key_id FROM llm_api_keys WHERE api_key = '{api_key}' and is_use = 1 and is_delete = 0"
    result = await db_client.select(sql)
    if not result:
        raise HTTPException(status_code=401, detail='api key error!')

    return result[0]['api_key_id']

# 参数校验
def validate_chat_params(params: dict):
    """校验chat参数"""
    if 'model' not in params:
        raise HTTPException(status_code=400, detail='model params error!')
    model = get_model(params['model'])
    if not model:
        raise HTTPException(status_code=500, detail='model params error!')

    if 'messages' not in params:
        raise HTTPException(status_code=400, detail='messages params error!')
    if not params['messages']:
        raise HTTPException(status_code=400, detail='messages params error!')
    if 'stream' in params and params['stream'] == True and 'stream_options' not in params:
        params['stream_options'] = {'include_usage': True}

    # 自定义web_search参数，并使用response接口，支持 火山云 供应商模型
    # https://www.volcengine.com/docs/82379/1756990?lang=zh
    if params.get('web_search', 'false').lower() == 'true':
        params['tools'] = params.get('tools', []) + [{'type': 'web_search'}]
        del params['web_search']

    return params


# 定义路由和视图函数
@app.get('/v1/models')
@app.get('/models')
async def list_models(request: Request):
    # 校验key
    api_key = request.headers.get('Authorization')
    await check_api_key(api_key)
    
    # 获取所有唯一模型名称
    unique_models = set()
    for model_name in MODELS_OBJ['models_dict'].keys():
        # 排除重复的model_id和model_name，只保留用户可见的模型名称
        # 避免同时返回model_name和model_id导致重复
        if ':' in model_name and model_name.endswith(':online'):
            # 保留OpenRouter的在线模型
            unique_models.add(model_name)
        elif not any(model_name == m.split(':')[0] for m in unique_models if m.endswith(':online')):
            unique_models.add(model_name)
    
    # 构造OpenAI标准响应格式
    models = []
    for model_name in sorted(unique_models):
        models.append({
            "id": model_name,
            "object": "model",
            "created": 1677610602,  # 固定时间戳，符合OpenAI格式
            "owned_by": "personal-llm",
            "permission": [
                {
                    "id": "modelperm-" + model_name,
                    "object": "model_permission",
                    "created": 1677610602,
                    "allow_create_engine": False,
                    "allow_sampling": True,
                    "allow_logprobs": True,
                    "allow_search_indices": False,
                    "allow_view": True,
                    "allow_fine_tuning": False,
                    "organization": "*",
                    "group": None,
                    "is_blocking": False
                }
            ],
            "root": model_name,
            "parent": None
        })
    
    return {
        "object": "list",
        "data": models
    }


@app.post('/v1/chat/completions')
@app.post('/chat/completions')
async def chat_completions(request: Request):
    # 校验key
    api_key = request.headers.get('Authorization')
    api_key_id = await check_api_key(api_key)

    # 接收请求体
    req = await request.json()
    # 校验参数
    req = validate_chat_params(req)
    req['api_key_id'] = api_key_id

    # 1. 获取模型
    model = get_model(req['model'])
    del req['model']

    # 2. 判断是否是流式
    if req.get('stream', False):
        # 流式
        return StreamingResponse(chat_stream(model, req), media_type="text/event-stream")
    else:
        # 非流式
        try:
            answer = await model.chat(req)
        except Exception as e:
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))
        return answer


async def img_params_process(img_params: list):
    """处理图片参数"""
    params = {}
    content = []
    images = []
    for item in img_params:
        if item[0] == 'prompt':
            content.append({'type': 'text', 'text': item[1]})
        elif 'image' in item[0]:
            if isinstance(item[1], list) or isinstance(item[1], str):
                if isinstance(item[1], str):
                    item[1] = [item[1]]
                for img in item[1]:
                    images.append({'type': 'image_url', 'image_url': {'url': img}})
            else:
                contents = await item[1].read()
        
                # 2. 将二进制数据转换为 Base64 编码的 bytes
                base64_bytes = base64.b64encode(contents)
                
                # 3. 将 bytes 转换为 utf-8 字符串
                base64_string = base64_bytes.decode("utf-8")
                
                # (可选) 构造 Data URI 格式，方便前端直接展示
                # 格式为：data:<mime_type>;base64,<data>
                mime_type = item[1].content_type
                full_base64_str = f"data:{mime_type};base64,{base64_string}"
                images.append({'type': 'image_url', 'image_url': {'url': full_base64_str}})
        else:
            params[item[0]] = item[1]
    
    content.extend(images)
    params['messages'] = [{'role': 'user', 'content': content}]

    return params

# 图片编辑和生成
@app.post('/v1/images/edits')
@app.post('/v1/images/generations')
async def chat_completions(request: Request):
    # 校验key
    api_key = request.headers.get('Authorization')
    api_key_id = await check_api_key(api_key)

    content_type = request.headers.get('Content-Type', '')

    # 接收请求体
    if 'multipart/form-data' in content_type:
        # 多部分表单数据
        img_params = await request.form()
        req = await img_params_process(img_params._list)
    else:
        img_params = await request.json()
        req = await img_params_process([(k, v) for k, v in img_params.items()])

    # 校验参数
    req = validate_chat_params(req)
    req['api_key_id'] = api_key_id

    # 1. 获取模型
    model = get_model(req['model'])
    del req['model']

    # 2. 判断是否是流式
    if req.get('stream', False):
        # 流式
        return StreamingResponse(chat_stream(model, req), media_type="text/event-stream")
    else:
        # 非流式
        try:
            answer = await model.chat(req)
        except Exception as e:
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))
        return answer


# 定义dashboard入口
@app.get('/dashboard/{path:path}')
async def dashboard(request: Request, path: str):

    # 获取session
    session = request.session

    if path == 'login':
        return FileResponse(os.path.join(settings.PROJECT_PATH, 'dashboard', 'login.html'))

    # 检查是否登录
    if 'user_id' not in session:
        # 未登录，返回登录页面
        return RedirectResponse(url="/dashboard/login")

    if path == 'reset-password':
        return FileResponse(os.path.join(settings.PROJECT_PATH, 'dashboard', 'reset_password.html'))
    elif path == 'home' or path == '':
        return FileResponse(os.path.join(settings.PROJECT_PATH, 'dashboard', f'index.html'))
    else:
        return FileResponse(os.path.join(settings.PROJECT_PATH, 'dashboard', f'{path}'))



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=2321)
