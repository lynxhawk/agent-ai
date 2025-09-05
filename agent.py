import os
from dotenv import load_dotenv
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from tools import upload_and_diagnose_file, check_file_format, test_api_connection

# 加载环境变量
load_dotenv()

class FaultDiagnosisAgent:
    def __init__(self, api_key: str = None, base_url: str = None):
        """
        初始化故障诊断Agent
        
        Args:
            api_key: DeepSeek API密钥
            base_url: API基础URL
        """
        # 优先使用传入的参数，否则使用环境变量
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        
        if not self.api_key:
            raise ValueError("请设置DEEPSEEK_API_KEY环境变量或传入api_key参数")
        
        print(f"🔗 连接到DeepSeek API: {self.base_url}")
        
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            model="deepseek-chat",
            temperature=0.1
        )
        
        # 定义工具
        self.tools = [upload_and_diagnose_file, check_file_format, test_api_connection]
        
        # 创建prompt模板
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的风机轴承故障诊断助手。你的主要职责是：

🎯 **核心功能**：
1. 帮助用户上传和分析风机轴承数据文件（支持txt和csv格式）
2. 调用故障诊断API (http://127.0.0.1:8000/diagnose) 进行分析
3. 向用户清晰地解释诊断结果
4. 提供相关的故障处理建议

🔄 **标准工作流程**：
1. 当用户提到故障诊断时，首先询问数据文件路径
2. 使用 check_file_format 工具检查文件格式和内容
3. 可选：使用 test_file_upload_api 进行上传测试（对于大文件推荐）
4. 确认文件无误后，使用 upload_and_diagnose_file 工具进行诊断
5. 清晰解释诊断结果并提供专业建议
6. 如果API连接有问题，使用 test_api_connection 工具检查连接状态

📁 **文件上传方式**：
- 使用form-data格式上传文件
- key为"file"，类型为File
- 支持大文件上传（如270k+行的CSV文件）
- 自动设置正确的Content-Type

🗣️ **交流风格**：
- 使用专业但易懂的语言
- 用emoji让界面更友好
- 对诊断结果进行详细解释
- 提供实用的维护建议

⚠️ **注意事项**：
- 只支持 .txt 和 .csv 格式的文件
- 诊断API地址为 http://127.0.0.1:8000/diagnose
- 如果用户没有提供文件路径，要主动询问
- 遇到错误时，要给出明确的解决建议

请始终保持专业、友好、有用的态度！"""),
            ("user", "{input}"),
            ("assistant", "{agent_scratchpad}")
        ])
        
        # 创建agent
        self.agent = create_openai_tools_agent(self.llm, self.tools, self.prompt)
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=10,
            return_intermediate_steps=True
        )
        
        print("✅ Agent初始化完成！")
    
    def chat(self, message: str) -> str:
        """
        与Agent对话
        
        Args:
            message: 用户消息
            
        Returns:
            Agent回复
        """
        try:
            print(f"🤔 用户输入：{message}")
            response = self.agent_executor.invoke({"input": message})
            return response["output"]
        except Exception as e:
            error_msg = f"❌ 处理请求时出错：{str(e)}"
            print(error_msg)
            return error_msg
    
    def get_welcome_message(self) -> str:
        """
        获取欢迎消息
        """
        return """🤖 **风机轴承故障诊断Agent已启动！**

我可以帮你：
• 🔸 **单文件诊断**：分析单个风机轴承数据文件
• 🔸 **批量诊断**：同时分析多个文件，提高效率
• 🔍 **格式检查**：验证文件格式和内容预览
• 🔧 **连接测试**：检查API服务器状态

📁 **支持格式**：.txt 和 .csv 文件

💬 **使用方法**：
- 单文件：`诊断文件：/path/to/data.csv`
- 批量：`批量诊断：file1.csv,file2.csv,file3.txt`
- 检查：`检查文件格式：/path/to/data.csv`

🔧 **API接口**：
- 单文件：http://127.0.0.1:8000/diagnose
- 批量：http://127.0.0.1:8000/diagnose-batch

开始使用吧！🚀"""

# 使用示例
if __name__ == "__main__":
    try:
        print("🚀 启动风机轴承故障诊断Agent...")
        agent = FaultDiagnosisAgent()
        
        print(agent.get_welcome_message())
        
        while True:
            user_input = input("\n👤 用户: ")
            
            if user_input.lower() in ['quit', 'exit', '退出', 'q']:
                print("👋 再见！")
                break
            
            if user_input.strip() == "":
                continue
                
            print("🤖 Agent正在思考...")
            response = agent.chat(user_input)
            print(f"\n🤖 Agent: {response}")
            
    except ValueError as e:
        print(f"❌ 配置错误: {e}")
        print("💡 请检查 .env 文件中的 DEEPSEEK_API_KEY 是否正确设置")
    except KeyboardInterrupt:
        print("\n👋 用户中断，再见！")
    except Exception as e:
        print(f"❌ 启动失败: {e}")