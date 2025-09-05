import requests
import pandas as pd
from langchain.tools import tool
from typing import Union
import os
import json
import tempfile

@tool
def upload_and_diagnose_file(file_path: str) -> str:
    """
    上传文件并进行风机轴承故障诊断
    
    Args:
        file_path: 文件路径，支持txt或csv格式
    
    Returns:
        诊断结果
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return f"错误：文件 {file_path} 不存在"
        
        # 检查文件格式
        if not file_path.lower().endswith(('.txt', '.csv')):
            return "错误：只支持txt或csv格式的文件"
        
        # 调用诊断API
        api_url = "http://127.0.0.1:8000/diagnose"
        
        print(f"📤 正在上传文件到API: {api_url}")
        print(f"📁 文件路径: {file_path}")
        print(f"📋 使用form-data格式，key='file'")
        
        # 使用form-data方式上传文件
        with open(file_path, 'rb') as file:
            # 构建files字典 - 这就是form-data格式的核心
            files = {
                'file': (
                    os.path.basename(file_path),  # 文件名
                    file,                         # 文件对象
                    'text/csv' if file_path.lower().endswith('.csv') else 'text/plain'  # MIME类型
                )
            }
            
            print(f"   - key: 'file'")
            print(f"   - filename: {os.path.basename(file_path)}")
            print(f"   - content-type: {files['file'][2]}")
            
            # 发送POST请求 - 使用files参数会自动创建multipart/form-data
            response = requests.post(
                api_url,
                files=files,  # 这里使用files参数，不是json参数！
                timeout=60    # 增加超时时间，支持大文件
            )
        
        print(f"📡 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                # 格式化返回结果
                formatted_result = format_diagnosis_result(result)
                return formatted_result
            except json.JSONDecodeError:
                # 如果返回的不是JSON格式
                return f"✅ 诊断完成！\n📋 服务器响应：{response.text}"
        else:
            return f"❌ API调用失败\n📊 状态码：{response.status_code}\n💬 错误信息：{response.text}"
            
    except requests.exceptions.ConnectionError:
        return "❌ 无法连接到诊断服务器 (http://127.0.0.1:8000)，请确保服务器正在运行"
    except requests.exceptions.Timeout:
        return "❌ 请求超时，诊断服务可能正在处理大量数据（270k+行数据需要较长时间）"
    except requests.exceptions.RequestException as e:
        return f"❌ 网络请求错误：{str(e)}"
    except Exception as e:
        return f"❌ 未知错误：{str(e)}"

@tool
def check_file_format(file_path: str) -> str:
    """
    检查文件格式和内容预览
    
    Args:
        file_path: 文件路径
    
    Returns:
        文件信息
    """
    try:
        if not os.path.exists(file_path):
            return f"❌ 文件 {file_path} 不存在"
        
        file_size = os.path.getsize(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path)
        
        info = f"📁 文件信息：\n"
        info += f"• 文件名：{file_name}\n"
        info += f"• 大小：{file_size:,} 字节 ({file_size/1024:.1f} KB)\n"
        info += f"• 格式：{file_ext}\n"
        
        # 检查格式是否支持
        if file_ext not in ['.txt', '.csv']:
            info += f"⚠️  警告：不支持的文件格式 {file_ext}，只支持 .txt 和 .csv\n"
            return info
        
        # 预览文件内容
        if file_ext == '.csv':
            try:
                df = pd.read_csv(file_path)
                info += f"• CSV行数：{len(df):,}\n"
                info += f"• 列数：{len(df.columns)}\n"
                info += f"• 列名：{', '.join(df.columns.astype(str))}\n"
                
                # 检查数据类型
                numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                if numeric_cols:
                    info += f"• 数值列：{', '.join(numeric_cols)}\n"
                
                info += f"\n📊 数据预览（前3行）：\n"
                info += df.head(3).to_string(index=False)
                
                # 检查是否有缺失值
                missing_data = df.isnull().sum()
                if missing_data.any():
                    info += f"\n⚠️  缺失值检查：\n"
                    for col, missing_count in missing_data[missing_data > 0].items():
                        info += f"• {col}: {missing_count} 个缺失值\n"
                
            except Exception as e:
                info += f"❌ CSV读取错误：{str(e)}\n"
        
        elif file_ext == '.txt':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    total_lines = len(lines)
                    
                info += f"• 总行数：{total_lines:,}\n"
                
                # 尝试检测是否为数值数据
                try:
                    # 检查前几行是否为数值
                    sample_lines = lines[:min(5, total_lines)]
                    numeric_lines = 0
                    for line in sample_lines:
                        line = line.strip()
                        if line:
                            try:
                                float(line)
                                numeric_lines += 1
                            except ValueError:
                                # 检查是否为多列数值数据（空格或逗号分隔）
                                parts = line.replace(',', ' ').split()
                                if len(parts) > 1:
                                    try:
                                        [float(p) for p in parts]
                                        numeric_lines += 1
                                    except ValueError:
                                        pass
                    
                    if numeric_lines > 0:
                        info += f"• 数值行检测：{numeric_lines}/{len(sample_lines)} 行似乎包含数值数据\n"
                
                except Exception:
                    pass
                
                info += f"\n📄 内容预览（前5行）：\n"
                preview_lines = lines[:5]
                for i, line in enumerate(preview_lines, 1):
                    info += f"{i:2d}: {line.rstrip()}\n"
                
                if total_lines > 5:
                    info += f"... 还有 {total_lines - 5} 行\n"
                    
            except Exception as e:
                info += f"❌ TXT读取错误：{str(e)}\n"
        
        info += f"\n✅ 文件格式检查完成，可以进行故障诊断"
        return info
        
    except Exception as e:
        return f"❌ 检查文件时出错：{str(e)}"

@tool 
def test_api_connection() -> str:
    """
    测试故障诊断API连接状态
    
    Returns:
        连接状态信息
    """
    try:
        api_url = "http://127.0.0.1:8000"
        
        # 先尝试ping根路径
        response = requests.get(api_url, timeout=5)
        
        if response.status_code == 200:
            return f"✅ API服务器连接正常 ({api_url})"
        else:
            return f"⚠️  API服务器响应异常，状态码：{response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return f"❌ 无法连接到API服务器 ({api_url})，请检查服务器是否启动"
    except requests.exceptions.Timeout:
        return f"❌ 连接超时，API服务器可能响应缓慢"
    except Exception as e:
        return f"❌ 连接测试失败：{str(e)}"

@tool
def test_file_upload_api(file_path: str) -> str:
    """
    测试文件上传API功能（不进行实际诊断，只测试上传）
    
    Args:
        file_path: 测试文件路径
    
    Returns:
        上传测试结果
    """
    try:
        if not os.path.exists(file_path):
            return f"❌ 测试文件 {file_path} 不存在"
        
        # 创建一个小的测试文件或使用原文件的前几行
        api_url = "http://127.0.0.1:8000/diagnose"
        
        print(f"🧪 测试文件上传到: {api_url}")
        
        # 如果是CSV文件，创建一个小的测试样本
        if file_path.lower().endswith('.csv'):
            try:
                # 读取原文件的前10行作为测试
                df = pd.read_csv(file_path, nrows=10)
                test_content = df.to_csv(index=False)
                
                # 创建临时测试文件
                with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
                    temp_file.write(test_content)
                    temp_file_path = temp_file.name
                
                # 上传测试文件 - 使用form-data格式
                with open(temp_file_path, 'rb') as file:
                    files = {
                        'file': ('test_sample.csv', file, 'text/csv')
                    }
                    
                    response = requests.post(
                        api_url,
                        files=files,  # 使用files参数，不是json
                        timeout=30
                    )
                
                # 清理临时文件
                os.unlink(temp_file_path)
                
            except Exception as e:
                return f"❌ 创建测试文件时出错：{str(e)}"
        else:
            # 对于txt文件，直接使用原文件进行测试
            with open(file_path, 'rb') as file:
                files = {
                    'file': (os.path.basename(file_path), file, 'text/plain')
                }
                
                response = requests.post(
                    api_url,
                    files=files,  # 使用files参数，不是json
                    timeout=30
                )
        
        if response.status_code == 200:
            return f"✅ 文件上传测试成功！\n📊 服务器响应状态: {response.status_code}\n💬 响应内容: {response.text[:200]}..."
        else:
            return f"⚠️  上传测试完成，但状态异常\n📊 状态码: {response.status_code}\n❌ 错误信息: {response.text}"
            
    except requests.exceptions.ConnectionError:
        return "❌ 无法连接到API服务器，请检查服务器是否启动"
    except requests.exceptions.Timeout:
        return "❌ 上传测试超时"
    except Exception as e:
        return f"❌ 上传测试失败：{str(e)}"

def format_diagnosis_result(result, diagnosis_type="诊断"):
    """
    格式化诊断结果，使其更易读
    
    Args:
        result: API返回的原始结果
        diagnosis_type: 诊断类型（单文件诊断/批量诊断）
        
    Returns:
        格式化后的结果字符串
    """
    try:
        if isinstance(result, dict):
            formatted = f"🔍 **{diagnosis_type}结果**\n\n"
            
            # 如果有状态信息
            if 'status' in result:
                if result['status'] == 'success':
                    formatted += "✅ 诊断状态：成功\n\n"
                else:
                    formatted += f"❌ 诊断状态：{result['status']}\n\n"
            
            # 如果有诊断结果
            if 'diagnosis' in result:
                formatted += f"📊 诊断结论：{result['diagnosis']}\n\n"
            
            # 如果有置信度
            if 'confidence' in result:
                confidence = result['confidence']
                if isinstance(confidence, (int, float)):
                    formatted += f"🎯 置信度：{confidence:.2%}\n\n"
                else:
                    formatted += f"🎯 置信度：{confidence}\n\n"
            
            # 如果有详细信息
            if 'details' in result:
                formatted += f"📝 详细信息：\n{result['details']}\n\n"
            
            # 如果有建议
            if 'recommendations' in result:
                formatted += f"💡 建议措施：\n{result['recommendations']}\n\n"
            
            # 添加其他字段
            for key, value in result.items():
                if key not in ['status', 'diagnosis', 'confidence', 'details', 'recommendations']:
                    formatted += f"• {key}：{value}\n"
            
            return formatted
        else:
            return f"📋 {diagnosis_type}结果：{str(result)}"
            
    except Exception as e:
        return f"📋 {diagnosis_type}完成，原始结果：{str(result)}\n\n注：结果格式化时出现问题：{str(e)}"

def format_batch_diagnosis_result(result, file_list):
    """
    格式化批量诊断结果，使其更易读
    
    Args:
        result: API返回的批量诊断结果
        file_list: 上传的文件列表
        
    Returns:
        格式化后的批量结果字符串
    """
    try:
        formatted = f"🔍 **批量诊断结果**\n\n"
        formatted += f"📦 处理文件数量：{len(file_list)}\n"
        formatted += f"📁 文件列表：\n"
        
        for i, file_path in enumerate(file_list, 1):
            formatted += f"  {i}. {os.path.basename(file_path)}\n"
        
        formatted += "\n"
        
        if isinstance(result, dict):
            # 如果有总体状态
            if 'status' in result:
                if result['status'] == 'success':
                    formatted += "✅ 批量诊断状态：成功\n\n"
                else:
                    formatted += f"❌ 批量诊断状态：{result['status']}\n\n"
            
            # 如果有批量结果列表
            if 'results' in result and isinstance(result['results'], list):
                formatted += "📊 **各文件诊断结果**：\n\n"
                
                for i, file_result in enumerate(result['results']):
                    file_name = os.path.basename(file_list[i]) if i < len(file_list) else f"文件{i+1}"
                    formatted += f"🔸 **{file_name}**\n"
                    
                    if isinstance(file_result, dict):
                        if 'diagnosis' in file_result:
                            formatted += f"   📋 诊断：{file_result['diagnosis']}\n"
                        if 'confidence' in file_result:
                            confidence = file_result['confidence']
                            if isinstance(confidence, (int, float)):
                                formatted += f"   🎯 置信度：{confidence:.2%}\n"
                            else:
                                formatted += f"   🎯 置信度：{confidence}\n"
                        if 'status' in file_result:
                            formatted += f"   📊 状态：{file_result['status']}\n"
                    else:
                        formatted += f"   📋 结果：{str(file_result)}\n"
                    
                    formatted += "\n"
            
            # 如果有总体统计
            if 'summary' in result:
                formatted += f"📈 **总体统计**：\n{result['summary']}\n\n"
            
            # 如果有批量建议
            if 'recommendations' in result:
                formatted += f"💡 **批量建议**：\n{result['recommendations']}\n\n"
            
            # 添加其他字段
            for key, value in result.items():
                if key not in ['status', 'results', 'summary', 'recommendations']:
                    formatted += f"• {key}：{value}\n"
        
        else:
            formatted += f"📋 原始结果：{str(result)}\n"
        
        return formatted
        
    except Exception as e:
        return f"📋 批量诊断完成，处理了 {len(file_list)} 个文件\n原始结果：{str(result)}\n\n注：结果格式化时出现问题：{str(e)}"