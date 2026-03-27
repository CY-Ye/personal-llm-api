import json

from dashscope import get_tokenizer

from service.llm_service import LLMService

# 获取tokenizer对象，目前只支持通义千问系列模型
qwen_tokenizer = get_tokenizer('qwen-coder')

# 通义千问供应商模型接口
# https://bailian.console.aliyun.com/?spm=5176.29597918.nav-v2-dropdown-menu-0.d_main_2_0_0.612a7b086WqU6B&tab=model&scm=20140722.M_10904466._.V_1#/model-market
class QwenLLMService(LLMService):

    # 获取usage
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

            query_token = qwen_tokenizer.encode(query)
            answer_token = qwen_tokenizer.encode(answer)

            data = {}
            data['prompt_tokens'] = len(query_token)
            data['completion_tokens'] = len(answer_token)
            data['total_tokens'] = data['prompt_tokens'] + data['completion_tokens']
            data['cached_tokens'] = 0
            data['cached_price'] = 0
            return data



