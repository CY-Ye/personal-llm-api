import json

import httpx

from service.llm_service import LLMService

# OpenRouter供应商模型接口
# https://openrouter.ai/docs/usage/chat-completions
class OpenRouterLLMService(LLMService):

    # # 根据不同的供应商参数进行个性化处理
    async def handle_params(self, params):

        # if params['model'] in ['openai/gpt-5.2', 'openai/gpt-5.2-chat', 'openai/gpt-5.2-pro']:
        if params.get('reasoning_effort', ''):
            if params['reasoning_effort'] not in ['none', 'low', 'medium', 'high', 'xhigh']:
                params['reasoning'] = {'enabled': True}
                del params['reasoning_effort']


    async def get_usage(self, response, params, answer):
        if response['usage']:
            completion_tokens = response['usage']['completion_tokens']

            if self.model_id == 'google/gemini-3-pro-image-preview':
                rate = 120 / 12
                if 'completion_tokens_details' in response['usage'] and 'image_tokens' in response['usage']['completion_tokens_details']:
                    image_tokens = response['usage']['completion_tokens_details']['image_tokens']
                    completion_tokens += image_tokens * rate

            cached_tokens = self._extract_cached_tokens(response['usage'])
            cached_price = self.cached_unit_price * (cached_tokens / 1000) if cached_tokens > 0 and self.cached_unit_price > 0 else 0

            return {
                'completion_tokens': completion_tokens,
                'prompt_tokens': response['usage']['prompt_tokens'],
                'total_tokens': response['usage']['prompt_tokens'] + completion_tokens,
                'cached_tokens': cached_tokens,
                'cached_price': cached_price
            }
        else:
            payload = {
                "id": params['id']
            }

            headers = {
                "Authorization": f"Bearer {self.key}"
            }

            # 异步请求session
            async with httpx.AsyncClient() as client:
                res = await client.get(f"{self.base_url.replace('/chat/completions', '/generation')}", json=payload, headers=headers)

            res = res.json()

            data = {}
            data['prompt_tokens'] = res['data']['tokens_prompt']
            data['completion_tokens'] = res['data']['tokens_completion']
            data['total_tokens'] = data['prompt_tokens'] + data['completion_tokens']
            data['cached_tokens'] = 0
            data['cached_price'] = 0
            return data



