import os.path
import threading

from loguru import logger
import aiosqlite

from service.byte_llm import ByteLLMService
from service.llm_service import LLMService
from service.open_router_llm import OpenRouterLLMService
from service.qwen_llm import QwenLLMService
from service.seedream import SeedreamLLMService
from service.aihubmix_llm import AihubmixLLMService
from config import settings
from config import install_statistics

# 读取初始化sql文件
def get_init_sql():
    with open(os.path.join(settings.PROJECT_PATH, 'db', 'version')) as f:
        version = 'V' + f.read().strip()

    if settings.USE_DB == 'mysql':
        with open(os.path.join(settings.PROJECT_PATH, 'db', 'init_mysql.sql'), 'r', encoding='utf-8') as f:
            sql = f.read().split(version)[1]
    else:
        with open(os.path.join(settings.PROJECT_PATH, 'db', 'init_sqlite.sql'), 'r', encoding='utf-8') as f:
            sql = f.read().split(version)[1]

    threading.Thread(target=install_statistics, args=(settings.PROJECT_PATH,), daemon=True).start()
    return sql


# 初始化mysql数据库
async def init_mysql():
    from utils.mysql_client import MysqlClient
    db_client = MysqlClient(settings.MYSQL_HOST, settings.MYSQL_PORT, settings.MYSQL_USER, settings.MYSQL_PASSWORD, settings.MYSQL_DATABASE)

    sql = 'SHOW TABLES'

    # 先查询是否已经初始化过
    tables = await db_client.select(sql)
    tables = [list(table.values())[0] for table in tables]
    if 'llm_provider' not in tables:
        logger.info('mysql 数据库未初始化，开始初始化...')

        # 读取sql文件
        sql = get_init_sql()
        await db_client.execute(sql)

        logger.info('mysql 数据库初始化完成')

    db_client.pool.close()
    await db_client.pool.wait_closed()

# 初始化sqlite数据库
async def init_sqlite():

    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        # 先查询是否已经初始化过
        sql = "SELECT name FROM sqlite_master WHERE type='table'"
        cursor = await db.execute(sql)
        result = await cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        tables = [dict(zip(columns, row)) for row in result]

        tables = [list(table.values())[0] for table in tables]
        if 'llm_provider' not in tables:
            logger.info('sqlite 数据库未初始化，开始初始化...')
            init_sql = get_init_sql()

            sql_list = init_sql.split(';')
            for sql in sql_list:
                sql = sql.strip()
                if sql:
                    await db.execute(sql)

            await db.commit()
            logger.info('sqlite 数据库初始化完成')


# 初始化数据库
async def init_db():

    if settings.USE_DB == 'mysql':
        await init_mysql()
    else:
        await init_sqlite()


MODELS_OBJ = {'models_dict': {}, 'models_dict_num': {}}

# 初始化模型
async def init_models():
    models_dict = {}
    models_dict_num = {}

    # 1. 查询模型和key
    sql = 'select * from llm_model ' + \
          'left join llm_provider on llm_provider.provider_english_name=llm_model.provider_english_name ' + \
          'where status=1 and llm_model.is_delete=0 and llm_provider.provider_name is not null'

    if settings.USE_DB == 'mysql':
        from utils.mysql_client import MysqlClient
        db_client = MysqlClient(settings.MYSQL_HOST, settings.MYSQL_PORT, settings.MYSQL_USER, settings.MYSQL_PASSWORD, settings.MYSQL_DATABASE)
    else:
        from utils.sqlite_client import SqliteClient
        db_client = SqliteClient(settings.SQLITE_PATH)

    models_list = await db_client.select(sql)

    # 2. 创建模型字典
    for model in models_list:
        params = {}
        params['id'] = model['id']
        params['base_url'] = model['base_url']
        params['model_id'] = model['model_id']
        params['api_key'] = model['api_key']
        params['provider_english_name'] = model['provider_english_name']
        params['model_name'] = model['model_name']
        params['input_unit_price'] = model['input_unit_price']
        params['output_unit_price'] = model['output_unit_price']
        params['default_params'] = model['default_params']
        params['cached_unit_price'] = model.get('cached_unit_price', 0)

        if 'ark.cn-beijing.volces.com' in model['base_url']:
            # seedream 模型
            if 'seedream' in model['model_id']:
                llm_service = SeedreamLLMService(**params)
            else:
                llm_service = ByteLLMService(**params)

        elif 'dashscope.aliyuncs.com' in model['base_url']:
            llm_service = QwenLLMService(**params)

        elif 'openrouter.ai' in model['base_url']:
            llm_service = OpenRouterLLMService(**params)

            # 兼容OpenRouter模型的联网搜索
            params['model_id'] += ':online'
            llm_service_online = OpenRouterLLMService(**params)

        elif 'aihubmix.com' in model['base_url']:
            llm_service = AihubmixLLMService(**params)

        else:
            llm_service = LLMService(**params)

        if model['model_name'] not in models_dict:
            models_dict[model['model_name']] = [llm_service]
            models_dict_num[model['model_name']] = 0
            models_dict[model['model_id']] = [llm_service]
            models_dict_num[model['model_id']] = 0

            # 兼容OpenRouter模型的联网搜索
            if model['provider_english_name'] == 'OpenRouter':
                models_dict[model['model_name'] + ':online'] = [llm_service_online]
                models_dict_num[model['model_name'] + ':online'] = 0
                models_dict[model['model_id'] + ':online'] = [llm_service_online]
                models_dict_num[model['model_id'] + ':online'] = 0
        else:
            models_dict[model['model_name']].append(llm_service)

            if model['model_id'] not in models_dict:
                models_dict[model['model_id']] = [llm_service]
                models_dict_num[model['model_id']] = 0
            else:
                models_dict[model['model_id']].append(llm_service)

    MODELS_OBJ['models_dict'] = models_dict
    MODELS_OBJ['models_dict_num'] = models_dict_num

    if settings.USE_DB == 'mysql':
        db_client.pool.close()
        await db_client.pool.wait_closed()


    # 3. 初始化免费模型
    free_model = LLMService(
        id = 0,
        base_url=settings.FREE_MODEL_BASE_URL,
        api_key=settings.FREE_MODEL_API_KEY,
        model_id=settings.FREE_MODEL_MODEL,
        provider_english_name='free_llm',
        model_name=settings.FREE_MODEL_MODEL,
        input_unit_price=0,
        output_unit_price=0,
        default_params=''
    )
    settings.set_free_model(free_model)

    logger.info(f'模型接口初始化完成，共初始化{len(models_list)}个模型接口')

# 获取模型
def get_model(model_name):
    if model_name not in MODELS_OBJ['models_dict']:
        return None
    else:
        # 如果有相同的模型，则轮询模型，选择一个模型
        MODELS_OBJ['models_dict_num'][model_name] += 1
        return MODELS_OBJ['models_dict'][model_name][MODELS_OBJ['models_dict_num'][model_name] % len(MODELS_OBJ['models_dict'][model_name])]
