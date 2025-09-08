import streamlit as st
import os
import tempfile
import requests
import datetime
from dotenv import load_dotenv

# 尝试导入 FaultDiagnosisAgent，如果失败则显示错误信息
try:
    from agent import FaultDiagnosisAgent
except ImportError as e:
    st.error(f"❌ 无法导入 FaultDiagnosisAgent: {e}")
    st.error("请检查 agent.py 文件是否存在且格式正确")
    st.stop()

# 加载环境变量
load_dotenv()

# 页面配置
st.set_page_config(
    page_title="风机轴承故障诊断Agent",
    page_icon="⚙️",
    layout="wide"
)

# 初始化session state
if 'messages' not in st.session_state:
    st.session_state.messages = []


def init_sidebar():
    """初始化侧边栏配置"""
    with st.sidebar:
        st.header("🔧 配置")

        # API Key配置
        auto_api_key = os.getenv("DEEPSEEK_API_KEY")
        if auto_api_key:
            st.success("✅ 已从环境变量加载API Key")
            api_key = auto_api_key
        else:
            api_key = st.text_input("DeepSeek API Key", type="password")

        # API连接测试
        st.subheader("🔗 连接测试")
        if st.button("测试API连接"):
            test_api_connection()

        # 初始化Agent
        if api_key:
            init_agent(api_key)

        return api_key


def test_api_connection():
    """测试API连接"""
    try:
        response = requests.get("http://127.0.0.1:8000", timeout=5)
        if response.status_code == 200:
            st.success("✅ 诊断API连接正常")
        else:
            st.warning(f"⚠️ API响应异常: {response.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("❌ 无法连接到 http://127.0.0.1:8000")
    except Exception as e:
        st.error(f"❌ 连接测试失败: {e}")


def init_agent(api_key):
    """初始化Agent"""
    if 'agent' not in st.session_state:
        try:
            st.session_state.agent = FaultDiagnosisAgent(api_key)
            st.success("🤖 Agent初始化成功！")
        except Exception as e:
            st.error(f"❌ Agent初始化失败：{e}")


def display_chat_history():
    """显示聊天历史"""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def save_temp_file(uploaded_file):
    """保存上传文件到临时目录"""
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=f".{uploaded_file.name.split('.')[-1]}"
    ) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        return tmp_file.name


def cleanup_temp_file(temp_path):
    """清理临时文件"""
    try:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    except:
        pass


def display_file_info(uploaded_file):
    """显示文件信息"""
    file_size = len(uploaded_file.getvalue())
    col1, col2 = st.columns(2)
    with col1:
        st.metric("文件大小", f"{file_size:,} 字节")
    with col2:
        st.metric("文件类型", uploaded_file.type)

    st.info(f"文件大小: {file_size:,} 字节 ({file_size/1024:.1f} KB)")


def is_diagnosis_request(user_input, api_key):
    """
    使用大模型判断用户输入是否是诊断请求
    """
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )

        system_prompt = """你是一个智能判断助手。你的任务是判断用户的输入是否是要求进行风机轴承故障诊断的请求。

判断标准：
- 如果用户明确要求诊断、分析数据文件、检测故障等，返回 "YES"
- 如果用户只是询问诊断相关的概念、原理、方法等理论问题，返回 "NO"
- 如果用户询问无关话题（天气、新闻、其他技术问题等），返回 "NO"

请只回答 "YES" 或 "NO"，不要有其他内容。

示例：
用户："请帮我诊断这个轴承数据" -> YES
用户："什么是故障诊断？" -> NO
用户："今天天气怎么样？" -> NO
用户："分析一下我上传的振动数据" -> YES
用户："风机轴承故障诊断的原理是什么？" -> NO
用户："帮我检测设备是否有问题" -> YES
"""

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            max_tokens=10,
            temperature=0.1
        )

        result = response.choices[0].message.content.strip().upper()
        return result == "YES"

    except Exception as e:
        print(f"语义判断失败: {e}")
        # 如果API调用失败，回退到关键词检测
        return fallback_keyword_detection(user_input)


def fallback_keyword_detection(user_input):
    """
    备用的关键词检测方法
    """
    diagnosis_keywords = ["诊断", "检测", "分析数据", "故障检测", "轴承分析"]
    non_diagnosis_keywords = ["是什么", "怎么", "为什么", "原理", "方法", "概念"]

    input_lower = user_input.lower()

    # 如果包含明确的非诊断关键词，返回False
    if any(keyword in input_lower for keyword in non_diagnosis_keywords):
        return False

    # 如果包含诊断关键词，返回True
    return any(keyword in input_lower for keyword in diagnosis_keywords)


def is_diagnosis_response(response_text, api_key):
    """
    使用大模型判断Agent回复是否是诊断结果
    """
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )

        system_prompt = """你是一个智能判断助手。你的任务是判断给定的文本是否是风机轴承故障诊断的结果报告。

判断标准：
- 如果文本包含具体的诊断数据、分析结果、故障状态、置信度等实际诊断内容，返回 "YES"
- 如果文本只是理论解释、概念说明、操作指导等，返回 "NO"
- 如果文本是普通对话回复，返回 "NO"

请只回答 "YES" 或 "NO"，不要有其他内容。

典型的诊断结果特征：
- 包含具体数值（置信度、异常分、预测值等）
- 包含诊断状态（正常/故障/异常）
- 包含分析指标和数据
- 结构化的诊断报告格式
"""

        # 只取前500字符进行判断，避免token过多
        text_sample = response_text[:500] if len(
            response_text) > 500 else response_text

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请判断这段文本是否是诊断结果：\n\n{text_sample}"}
            ],
            max_tokens=10,
            temperature=0.1
        )

        result = response.choices[0].message.content.strip().upper()
        return result == "YES"

    except Exception as e:
        print(f"诊断结果判断失败: {e}")
        # 如果API调用失败，回退到关键词检测
        return fallback_result_detection(response_text)


def fallback_result_detection(response_text):
    """
    备用的诊断结果检测方法
    """
    # 更严格的结构化检测
    return (
        ("诊断概况" in response_text and "详细分析指标" in response_text) or
        ("置信度得分" in response_text and "异常得分" in response_text) or
        ("使用模型" in response_text and (
            "IsolationForest" in response_text or "故障检测" in response_text))
    )


def display_diagnosis_report(diagnosis_result, title="📊 诊断结果报告"):
    """以优化格式显示诊断报告 - 使用改进的状态检测"""
    # 使用完整宽度的分割线
    st.markdown("---")

    # 直接使用 streamlit 的默认布局
    st.subheader(title)

    # 使用改进的状态分析
    status_type, status_message, status_level = analyze_diagnosis_status(
        diagnosis_result)

    # 根据分析结果显示状态
    if status_level == 'success':
        st.success(status_message)
    elif status_level == 'error':
        st.error(status_message)
    elif status_level == 'warning':
        st.warning(status_message)
    else:
        st.info(status_message)

    # 添加状态统计信息（可选）
    with st.expander("🔍 状态分析详情", expanded=False):
        st.markdown(f"**检测到的状态类型**: {status_type}")

        # 显示关键信息摘要
        if "故障" in diagnosis_result:
            fault_info = []
            lines = diagnosis_result.split('\n')
            for line in lines:
                if '故障' in line or '异常' in line:
                    fault_info.append(line.strip())

            if fault_info:
                st.markdown("**关键发现**:")
                for info in fault_info[:5]:  # 只显示前5条
                    st.markdown(f"- {info}")

    # 在一个扩展容器中显示完整报告内容
    with st.expander("📋 查看完整诊断报告", expanded=True):
        st.markdown(diagnosis_result)

    # 添加下载按钮
    current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        label="📥 下载诊断报告",
        data=diagnosis_result,
        file_name=f"故障诊断报告_{current_time}.txt",
        mime="text/plain",
        use_container_width=True
    )


def single_file_diagnosis():
    """单文件诊断功能"""
    st.markdown("**上传单个数据文件进行诊断**")

    uploaded_file = st.file_uploader(
        "选择风机轴承数据文件",
        type=['txt', 'csv'],
        help="支持txt和csv格式的数据文件。注意：大文件（如270k+行）上传可能需要较长时间。",
        key="single_file"
    )

    if uploaded_file is not None:
        display_file_info(uploaded_file)

        # 保存临时文件
        temp_file_path = save_temp_file(uploaded_file)
        st.success(f"📄 文件已上传：{uploaded_file.name}")

        # 如果Agent已初始化，显示操作按钮
        if 'agent' in st.session_state:
            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("🔍 检查文件格式", type="secondary", key="check_single"):
                    check_file_format(temp_file_path, uploaded_file.name)

            with col2:
                if st.button("🧪 测试上传", type="secondary", key="test_single"):
                    test_file_upload(temp_file_path, uploaded_file.name)

            with col3:
                if st.button("🚀 开始诊断", type="primary", key="diagnose_single"):
                    start_single_diagnosis(temp_file_path, uploaded_file.name)

        # 清理临时文件
        cleanup_temp_file(temp_file_path)


def batch_file_diagnosis():
    """批量文件诊断功能"""
    st.markdown("**批量上传多个文件进行诊断**")

    uploaded_files = st.file_uploader(
        "选择多个风机轴承数据文件",
        type=['txt', 'csv'],
        accept_multiple_files=True,
        help="可以同时选择多个txt或csv文件进行批量诊断",
        key="batch_files"
    )

    if uploaded_files:
        display_batch_file_info(uploaded_files)

        # 保存所有文件到临时目录
        temp_file_paths = []
        try:
            for uploaded_file in uploaded_files:
                temp_path = save_temp_file(uploaded_file)
                temp_file_paths.append(temp_path)

            # 如果Agent已初始化，显示操作按钮
            if 'agent' in st.session_state:
                col1, col2 = st.columns(2)

                with col1:
                    if st.button("🔍 检查所有文件格式", type="secondary", key="check_batch"):
                        check_batch_files_format(
                            uploaded_files, temp_file_paths)

                with col2:
                    if st.button("🚀 开始批量诊断", type="primary", key="diagnose_batch"):
                        start_batch_diagnosis(uploaded_files, temp_file_paths)

        finally:
            # 清理所有临时文件
            for temp_path in temp_file_paths:
                cleanup_temp_file(temp_path)


def display_batch_file_info(uploaded_files):
    """显示批量文件信息"""
    st.success(f"📦 已上传 {len(uploaded_files)} 个文件")

    total_size = 0
    with st.expander("📋 查看文件列表", expanded=True):
        for i, file in enumerate(uploaded_files, 1):
            file_size = len(file.getvalue())
            total_size += file_size
            st.write(
                f"{i}. **{file.name}** - {file_size:,} 字节 ({file_size/1024:.1f} KB)")

    st.info(f"总大小: {total_size:,} 字节 ({total_size/1024:.1f} KB)")


def check_file_format(temp_file_path, file_name):
    """检查文件格式"""
    with st.spinner("检查文件格式..."):
        file_info = st.session_state.agent.chat(
            f"检查文件格式，文件名：{file_name}，文件路径：{temp_file_path}")
        st.info(file_info)


def test_file_upload(temp_file_path, file_name):
    """测试文件上传"""
    with st.spinner("测试文件上传..."):
        test_result = st.session_state.agent.chat(
            f"测试文件上传，文件名：{file_name}，文件路径：{temp_file_path}")

        # 添加到消息历史
        add_to_chat_history("user", f"测试上传文件：{file_name}")
        add_to_chat_history("assistant", test_result)

        with st.chat_message("assistant"):
            st.markdown(test_result)


def start_single_diagnosis(temp_file_path, file_name):
    """开始单文件诊断"""
    with st.spinner("正在进行故障诊断...这可能需要一些时间..."):
        diagnosis_result = st.session_state.agent.chat(
            f"对文件 {file_name} 进行风机轴承故障诊断，文件路径：{temp_file_path}"
        )

        # 添加到消息历史
        add_to_chat_history("user", f"单文件诊断：{file_name}")
        add_to_chat_history("assistant", diagnosis_result)

    # 移除聊天界面显示，只使用全宽报告显示
    # 使用 session_state 存储诊断结果，在主函数中显示
    st.session_state.diagnosis_result = diagnosis_result
    st.session_state.diagnosis_title = "📊 单文件诊断结果报告"
    st.session_state.show_diagnosis = True


def check_batch_files_format(uploaded_files, temp_file_paths):
    """检查批量文件格式"""
    with st.spinner("检查所有文件格式..."):
        for i, (uploaded_file, temp_path) in enumerate(zip(uploaded_files, temp_file_paths)):
            st.write(f"**检查文件 {i+1}: {uploaded_file.name}**")
            file_info = st.session_state.agent.chat(
                f"检查文件格式，文件名：{uploaded_file.name}，文件路径：{temp_path}")
            st.info(file_info)
            if i < len(temp_file_paths) - 1:
                st.divider()


def start_batch_diagnosis(uploaded_files, temp_file_paths):
    """开始批量诊断"""
    with st.spinner(f"正在进行批量诊断...处理 {len(uploaded_files)} 个文件，请耐心等待..."):
        # 构建文件信息字符串，包含文件名和路径的映射
        file_info_list = []
        for uploaded_file, temp_path in zip(uploaded_files, temp_file_paths):
            file_info_list.append(f"文件名：{uploaded_file.name}，路径：{temp_path}")

        file_info_str = "；".join(file_info_list)
        diagnosis_result = st.session_state.agent.chat(
            f"批量诊断这些文件：{file_info_str}")

        # 添加到消息历史
        file_names = [f.name for f in uploaded_files]
        add_to_chat_history(
            "user", f"批量诊断 {len(uploaded_files)} 个文件：{', '.join(file_names)}")
        add_to_chat_history("assistant", diagnosis_result)

    # 移除聊天界面显示，只使用全宽报告显示
    # 使用 session_state 存储诊断结果，在主函数中显示
    st.session_state.diagnosis_result = diagnosis_result
    st.session_state.diagnosis_title = "📊 批量诊断结果报告"
    st.session_state.show_diagnosis = True


def add_to_chat_history(role, content):
    """添加消息到聊天历史"""
    st.session_state.messages.append({"role": role, "content": content})


def chat_interface():
    """聊天界面 - 使用语义判断"""
    if prompt := st.chat_input("有什么问题吗？"):
        if 'agent' not in st.session_state:
            st.error("请先在侧边栏输入DeepSeek API Key")
        else:
            # 获取API Key
            api_key = os.getenv("DEEPSEEK_API_KEY")

            # 添加用户消息
            add_to_chat_history("user", prompt)
            with st.chat_message("user"):
                st.markdown(prompt)

            # 获取Agent回复
            with st.chat_message("assistant"):
                with st.spinner("思考中..."):
                    response = st.session_state.agent.chat(prompt)

                    # 使用语义判断是否是诊断结果
                    if api_key and is_diagnosis_response(response, api_key):
                        st.markdown("**诊断完成！请查看下方的详细报告。**")
                        # 存储到 session_state 用于全宽显示
                        st.session_state.diagnosis_result = response
                        st.session_state.diagnosis_title = "🔍 风机轴承故障诊断结果分析"
                        st.session_state.show_diagnosis = True
                    else:
                        # 普通聊天回复正常显示
                        st.markdown(response)

            # 添加助手回复到历史
            add_to_chat_history("assistant", response)


def bottom_controls():
    """底部控制按钮"""
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("🗑️ 清除聊天记录"):
            st.session_state.messages = []
            st.rerun()

    with col2:
        if st.button("🔄 重启Agent"):
            if 'agent' in st.session_state:
                del st.session_state.agent
            st.rerun()

    with col3:
        status = "🟢 就绪" if 'agent' in st.session_state else "🔴 未初始化"
        st.markdown(f"**状态**: {status}")


def display_usage_guide():
    """显示使用指南"""
    with st.expander("📖 使用指南"):
        st.markdown("""
        ### 🚀 快速开始
        
        #### 🔸 单文件诊断
        1. 在"单文件诊断"标签页选择一个文件
        2. 点击"检查文件格式"确认文件内容正确
        3. 可选择"测试上传"验证API连接
        4. 点击"开始诊断"进行分析
        
        #### 📦 批量诊断
        1. 在"批量诊断"标签页选择多个文件
        2. 查看文件列表确认无误
        3. 可选择"检查所有文件格式"验证文件
        4. 点击"开始批量诊断"同时分析所有文件
        
        ### 📁 支持的文件格式
        - **CSV文件**: 振动数据表格，支持大文件（270k+行）
        - **TXT文件**: 文本格式的振动数据
        
        ### ⚙️ 技术细节
        - **单文件**: 上传到 `http://127.0.0.1:8000/diagnose`，key='file'
        - **批量**: 上传到 `http://127.0.0.1:8000/diagnose-batch`，key='files'
        - 文件通过 form-data 格式上传，自动设置正确的Content-Type
        - 批量诊断支持同时处理多个文件，提高效率
        
        ### 🛠️ 故障排除
        - 如果上传失败，先测试API连接
        - 大文件或批量上传需要更长时间，请耐心等待
        - 确保诊断服务器在对应端口运行
        - 批量诊断建议文件数量不超过10个，避免超时
        """)


def main():
    """主函数"""
    # 页面标题
    st.title("⚙️ 风机轴承故障诊断Agent")
    st.markdown("基于LangChain的智能故障诊断助手")

    # 初始化侧边栏
    api_key = init_sidebar()

    # 显示聊天历史（排除诊断结果，因为会在下方全宽显示）
    display_chat_history()

    # 文件上传区域
    st.subheader("📁 文件上传")

    # 添加标签页支持单文件和批量上传
    tab1, tab2 = st.tabs(["🔸 单文件诊断", "📦 批量诊断"])

    with tab1:
        single_file_diagnosis()

    with tab2:
        batch_file_diagnosis()

    # 在这里显示诊断报告 - 完全脱离tab布局，统一的全宽显示
    if hasattr(st.session_state, 'show_diagnosis') and st.session_state.show_diagnosis:
        display_diagnosis_report(
            st.session_state.diagnosis_result, st.session_state.diagnosis_title)
        # 显示后清除标志，避免重复显示
        st.session_state.show_diagnosis = False

    # 使用指南
    display_usage_guide()

    # 聊天界面
    chat_interface()

    # 底部控制按钮
    bottom_controls()

    # 页脚
    st.markdown("---")
    st.markdown("💡 **提示**: 批量诊断可以同时处理多个文件，大大提高分析效率！单个大文件建议先进行上传测试。")


if __name__ == "__main__":
    main()
