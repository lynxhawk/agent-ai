# test_config.py
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def test_config():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    
    print("=== 配置检查 ===")
    
    if api_key:
        print(f"✅ API Key已加载: {api_key[:10]}...{api_key[-4:]}")
    else:
        print("❌ API Key未找到")
        return False
    
    print(f"✅ Base URL: {base_url}")
    
    # 测试API连接
    try:
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model="deepseek-chat",
            temperature=0.1
        )
        
        # 发送简单测试消息
        response = llm.invoke("你好，请回复'连接成功'")
        print(f"✅ API连接测试成功: {response.content}")
        return True
        
    except Exception as e:
        print(f"❌ API连接测试失败: {e}")
        return False

if __name__ == "__main__":
    if test_config():
        print("\n🎉 配置完成！可以继续下一步")
    else:
        print("\n❌ 配置有问题，请检查.env文件")