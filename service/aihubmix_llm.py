import json
import os

import httpx
from PIL import Image
from google import genai
from google.genai import types

from service.llm_service import LLMService
from utils.logger import Logger
from utils.util import save_base64_image, snowflake
from config import settings

# 推理时代供应商模型接口
# https://docs.aihubmix.com/cn
class AihubmixLLMService(LLMService):

    def __init__(self, id, base_url, model_id, api_key, provider_english_name, model_name, input_unit_price, output_unit_price, default_params, cached_unit_price=0):
        super().__init__(id, base_url, model_id, api_key, provider_english_name, model_name, input_unit_price, output_unit_price, default_params, cached_unit_price)
        
        if settings.AIHUBMIX_DISCOUNT_CODE:
            self.headers['APP-Code'] = settings.AIHUBMIX_DISCOUNT_CODE
            self.stream_headers['APP-Code'] = settings.AIHUBMIX_DISCOUNT_CODE

    async def chat_stream(self, params):
        if self.model_id in ['gemini-3-pro-image-preview']:
            id = params.get('id', '')
            if id:
                del params['id']
            else:
                id = snowflake.next_id()

            history = await self.create_history(params)
            logger = Logger(self.model_name, id)
            logger.info(f"chat start")

            params['model'] = self.model_id
            if self.default_params: # 合并默认参数
                for key, value in self.default_params.items():
                    if key not in params:
                        params[key] = value
            
            response = await self.gemini_3_pro_image_preview(params)



        else:
            async for chunk in super().chat_stream(params):
                yield chunk

    # gemini_3_pro_image_preview 模型特殊处理
    async def gemini_3_pro_image_preview(self, params):
        # 转成google api参数
        contents = []
        for message in params['messages']:
            if isinstance(message['content'], list):
                for content_item in message['content']:
                    if 'image_url' in content_item:
                        if content_item['image_url']['url'].startswith('data:image'):
                            # 保存图片
                            image_url = content_item['image_url']['url']
                            img_path = save_base64_image(image_url.split(',')[1])
                            contents.append(Image.open(os.path.join(settings.PROJECT_PATH, img_path[1:])))
                    elif content_item['type'] == 'text':
                        contents.append(content_item['text'])
                
            else:
                contents.append(message['content'])
        
        # 开始请求
        client = genai.Client(
            api_key=self.key,
            http_options={"base_url": "https://aihubmix.com/gemini"}
        )

        

        response = await client.aio.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=['TEXT', 'IMAGE']
            )
        )

        for part in response.parts:
            if part.text is not None:
                print(part.text)
            elif image := part.as_image():
                image.save("office.png")
