import json
import time
import asyncio

import httpx
from fastapi.exceptions import HTTPException

from service.llm_service import LLMService
from utils.util import snowflake, save_base64_image, get_current_timestamp, extract_img_params, read_base64_img_size, resize_img_limit, get_resolution
from utils.logger import Logger
from utils.db_client import db_client
from config import settings

# doubao-seedream转chat模型接口
# https://www.volcengine.com/product/ark
resolution_ratio_dict = {'1k': 1024, '2k': 2048, '3k': 3072, '4k': 4096}

class SeedreamLLMService(LLMService):



    async def update_tokens(self, history, response, img_num):
        # 更新tokens
        reasoning_content = ''

        update_data = {}
        if response['usage']:
            update_data['completion_tokens'] = response['usage']['completion_tokens']
            update_data['prompt_tokens'] = response['usage']['prompt_tokens']
            update_data['input_price'] = self.input_unit_price * (response['usage']['prompt_tokens'] / 1000)
            update_data['output_price'] = self.output_unit_price * img_num
            # Handle cached_tokens - compute if not provided by API
            if 'cached_tokens' in response['usage']:
                update_data['cached_tokens'] = response['usage']['cached_tokens']
                update_data['cached_price'] = response['usage'].get('cached_price', 0)
            else:
                cached_tokens = self._extract_cached_tokens(response['usage'])
                update_data['cached_tokens'] = cached_tokens
                update_data['cached_price'] = self.cached_unit_price * (cached_tokens / 1000) if cached_tokens > 0 and self.cached_unit_price > 0 else 0
        else:
            update_data['completion_tokens'] = 0
            update_data['prompt_tokens'] = 0
            update_data['input_price'] = 0
            update_data['output_price'] = 0
            update_data['cached_tokens'] = 0
            update_data['cached_price'] = 0

        if not response['choices'][0]['message']['content']:
            response['choices'][0]['message']['content'] = ''
        update_data['answer'] = reasoning_content + response['choices'][0]['message']['content']

        current_timestamp = get_current_timestamp()
        update_data['update_time'] = current_timestamp[0:-4]

        await db_client.update('llm_chat_history', update_data, f'id={history["id"]}')


    async def chat_params_to_seedream(self, params):
        # 转换messages格式
        seedream_params = {}
        seedream_params['model'] = self.model_id
        seedream_params['prompt'] = ''
        seedream_params['sequential_image_generation'] = params.get('sequential_image_generation', 'auto')
        seedream_params['response_format'] = params.get('response_format', 'b64_json')
        seedream_params['watermark'] = params.get('watermark', False)
        image = []
        for key in params.keys():
            if key == 'messages':
                for item in params['messages']:
                    if item['role'] == 'user':
                        for content_item in item['content']:
                            if content_item['type'] == 'text':
                                seedream_params['prompt'] = content_item['text']
                            elif content_item['type'] == 'image_url':
                                image.append(content_item['image_url']['url'])
            elif key not in ['model', 'prompt', 'image', 'stream_options']:
                seedream_params[key] = params[key]
        
        if image:
            seedream_params['image'] = image
        

        if 'size' not in seedream_params:
            # 从query提取图片参数
            img_params = await extract_img_params(seedream_params['prompt'])
            
            if img_params['is_use_original_img_rate']:
                if not image:
                    raise HTTPException(status_code=400, detail="使用原始图片比例时，必须提供图片")
                
                width, height = await asyncio.to_thread(read_base64_img_size, image[0])
                resize_width, resize_height = resize_img_limit(width, height, limit=resolution_ratio_dict[img_params['resolution_ratio']])
                seedream_params['size'] = f'{resize_width}x{resize_height}'
            else:
                width, height = get_resolution(img_params['resolution_ratio'], aspect_ratio=img_params['rate'])
                seedream_params['size'] = f'{width}x{height}'
        
        return seedream_params


    async def chat(self, params):
        id = params.get('id', '')
        if id:
            del params['id']
        else:
            id = snowflake.next_id()

        history = await self.create_history(params)
        logger = Logger(self.model_name, id)
        logger.info(f"chat start")

        # httpx异步请求
        content = []
        params['model'] = self.model_id
        
        # chat接口转换成image接口参数
        seedream_params = await self.chat_params_to_seedream(params)
        
        async with httpx.AsyncClient(**settings.HTTPX_PARAMS) as client:
            response = await client.post(self.base_url + '/images/generations', json=seedream_params, headers=self.headers, timeout=600)
            if response.status_code != 200:
                # 先读取响应内容
                error_content = await response.aread()
                raise HTTPException(status_code=response.status_code, detail=error_content.decode())

        response = response.json()

        # 图片转存
        for img in response['data']:
            img_path = save_base64_image(img['b64_json'])
            content.append(f'\n\n![image]({img_path})')

        usage = await self.get_usage(response['usage'])

        # 记录数据
        res = {'id': history['id'],
                    'choices': [{'message': {
                        "role": "assistant",
                        'content': ''.join(content)
                    }}],
                    'usage': usage,
                    "created": int(time.time()), "model": self.model_id, "object": "chat.completion"
                    }

        await self.update_tokens(history, res, len(content))
        logger.info(f"chat end")

        return response


    async def chat_stream(self, params):
        id = params.get('id', '')
        if id:
            del params['id']
        else:
            id = snowflake.next_id()

        history = await self.create_history(params)
        logger = Logger(self.model_name, id)
        logger.info(f"chat start")

        # httpx异步请求
        usage = None
        content = []
        params['model'] = self.model_id
        
        # chat接口转换成image接口参数
        seedream_params = await self.chat_params_to_seedream(params)
        
        async with httpx.AsyncClient(**settings.HTTPX_PARAMS) as client:
            async with client.stream("POST", self.base_url + '/images/generations', json=seedream_params, headers=self.stream_headers) as response:
                if response.status_code != 200:
                    # 先读取响应内容
                    error_content = await response.aread()
                    raise HTTPException(status_code=response.status_code, detail=error_content.decode())

                async for line in response.aiter_lines():
                    chunk = line.strip()
                    # logger.info(f"chunk: {chunk}")
                    if not chunk:
                        continue  # 跳过空行

                    if 'event' in chunk:
                        yield chunk
                        continue  # 跳过空行

                    chunk = chunk[6:]
                    if chunk == '[DONE]':
                        continue  # 跳过空行

                    chunk = json.loads(chunk)
                    if chunk['type'] == 'image_generation.partial_succeeded':
                        img_path = save_base64_image(chunk['b64_json'])
                        content.append(f'\n\n![image]({img_path})')
                    elif chunk['type'] == 'image_generation.completed':
                        usage = chunk['usage']
                    
                    yield chunk


        usage = await self.get_usage(usage)

        # 记录数据
        response = {'id': history['id'],
                    'choices': [{'message': {
                        "role": "assistant",
                        'content': ''.join(content)
                    }}],
                    'usage': usage,
                    "created": int(time.time()), "model": self.model_id, "object": "chat.completion"
                    }

        await self.update_tokens(history, response, len(content))
        logger.info(f"chat end")

    async def get_usage(self, usage):
        return {'completion_tokens': usage['output_tokens'], 'prompt_tokens': 0, 'total_tokens': usage['total_tokens']}
    

    # async def seedream_result_to_chat(self, seedream_result: dict):
    #     """将seedream结果转换为chat模型格式"""
    #     templace = {"choices": [{"delta": {"content": "", "role": "assistant"}, "index": 0, "finish_reason": None}],
    #                     "created": int(time.time()), "model": self.model_id,
    #                     "service_tier": "default", "object": "chat.completion.chunk", "usage": None}

    #     if seedream_result['type'] == 'image_generation.partial_succeeded':                                                              
    #         # seedream_result['b64_json'] 加上前缀 data:image/png;base64,
    #         templace['choices'][0]['delta']['images'] = [{'image_type':'image_url', 'image_url': {'url': f"data:image/png;base64,{seedream_result['b64_json']}"}}]
    #         return templace
    #     elif seedream_result['type'] == 'image_generation.completed':
    #         if 'images' in templace['choices'][0]['delta']:
    #             del templace['choices'][0]['delta']['images']

    #         templace['usage'] = await self.get_usage(seedream_result['usage'])
    #         templace['choices'][0]['finish_reason'] = 'stop'
    #         return templace
    #     else:
    #         return templace




