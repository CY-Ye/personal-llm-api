import json

import httpx

from service.llm_service import LLMService

# 字节供应商模型接口
# https://www.volcengine.com/product/ark
class ByteLLMService(LLMService):

    async def get_usage(self, response, params, answer):
        if response['usage']:
            cached_tokens = self._extract_cached_tokens(response['usage'])
            cached_price = self.cached_unit_price * (cached_tokens / 1000) if cached_tokens > 0 and self.cached_unit_price > 0 else 0
            return {
                'completion_tokens': response['usage']['completion_tokens'],
                'prompt_tokens': response['usage']['prompt_tokens'],
                'total_tokens': response['usage']['total_tokens'],
                'cached_tokens': cached_tokens,
                'cached_price': cached_price
            }
        else:
            query = [msg['content'] for msg in params['messages'] if 'content' in msg]

            # 是否有function
            for item in params.get('tools', []):
                query.append(json.dumps(item, ensure_ascii=False, indent=4))
            query = '\n'.join(query)

            payload = {
                "model": params['model'],
                "text": [query, answer]
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.key}"
            }

            # 异步请求session
            async with httpx.AsyncClient() as client:
                res = await client.post(f"{self.base_url}/tokenization", json=payload, headers=headers)

            res = res.json()

            data = {}
            data['prompt_tokens'] = res['data'][0]['total_tokens']
            data['completion_tokens'] = res['data'][1]['total_tokens']
            data['total_tokens'] = res['data'][0]['total_tokens'] + res['data'][1]['total_tokens']
            data['cached_tokens'] = 0
            data['cached_price'] = 0
            return data



