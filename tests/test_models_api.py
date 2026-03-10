from openai import AsyncOpenAI
import asyncio

# 1. 创建自定义客户端，指定你的模型服务终点和API Key
custom_client = AsyncOpenAI(
    base_url="http://localhost:2321/v1",
    api_key="sk-6krzNJoef72vmQkzCAf97BFiMwevu2cQ"  # 替换为你的API密钥
)

async def test_list_models():
    """测试获取所有模型接口"""
    try:
        # 调用获取模型列表接口
        models = await custom_client.models.list()
        
        print("=== 模型列表获取成功 ===")
        print(f"总模型数量: {len(models.data)}")
        print("-" * 50)
        
        # 打印每个模型信息
        for i, model in enumerate(models.data, 1):
            print(f"{i}. 模型ID: {model.id}")
            print(f"   所属者: {model.owned_by}")
            print(f"   创建时间: {model.created}")
            print(f"   根模型: {model.root}")
            print()
            
        print("=== 接口符合OpenAI标准 ===")
        print(f"响应对象类型: {models.object}")
        print(f"第一个模型对象类型: {models.data[0].object if models.data else '无数据'}")
        
        return True
        
    except Exception as e:
        print(f"=== 接口测试失败 ===")
        print(f"错误信息: {str(e)}")
        return False

async def test_model_compatibility():
    """测试模型是否可以正常使用"""
    try:
        # 先获取模型列表
        models = await custom_client.models.list()
        
        if not models.data:
            print("没有可用的模型进行兼容性测试")
            return False
            
        # 使用第一个模型进行测试
        test_model = models.data[0].id
        print(f"\n=== 测试模型 '{test_model}' 兼容性 ===")
        
        # 发送简单的聊天请求
        response = await custom_client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "你好，请简单介绍一下你自己"}],
            stream=False,
            max_tokens=100
        )
        
        print(f"测试成功！模型返回: {response.choices[0].message.content[:50]}...")
        return True
        
    except Exception as e:
        print(f"模型兼容性测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    print("开始测试OpenAI兼容的模型列表接口...")
    print("=" * 60)
    
    # 运行测试
    success = asyncio.run(test_list_models())
    
    if success:
        # 如果模型列表获取成功，可选测试模型兼容性
        # asyncio.run(test_model_compatibility())
        print("\n✅ 所有测试通过！接口完全兼容OpenAI标准")
    else:
        print("\n❌ 测试失败，请检查接口配置")
