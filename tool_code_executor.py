import re
import os
import tempfile
import asyncio
import docker
import uuid
import time
import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from llama_index.core.tools import BaseTool,ToolOutput,AsyncBaseTool
from llama_index.core.tools.types import ToolMetadata
from llama_index.core.tools import FunctionTool
from docker_container import DockerContainer

# 全局变量 - Docker容器映射表（按用户ID组织）
_docker_containers: Dict[str, DockerContainer] = {}

# 任务目录映射（按用户ID和任务ID组织）
_task_directories: Dict[str, Dict[str, str]] = {}

# 基本工作目录
BASE_WORK_DIR = "/Users/pingcy/workspace/tasks"

def get_docker_container(
    user_id: str = "default",
    image: str = "python_code_executor:3.11",
    container_name: Optional[str] = None,
) -> DockerContainer:
    """获取或创建特定用户的Docker容器
    
    Args:
        user_id: 用户ID，用于区分不同用户
        image: Docker镜像名称
        container_name: 容器名称，如不提供则根据用户ID生成
        
    Returns:
        DockerContainer: 用户专属的容器实例
    """
    global _docker_containers
    
    # 如果不提供容器名称则根据用户ID生成
    if container_name is None:
        container_name = f"llamaindex-executor-{user_id}"
    
    # 为用户创建专属容器
    if user_id not in _docker_containers or _docker_containers[user_id] is None:
        _docker_containers[user_id] = DockerContainer(
            image=image,
            container_name=container_name,
            base_work_dir=os.path.join(BASE_WORK_DIR, user_id)
        )
        _docker_containers[user_id].start()
        
        # 确保用户基本工作目录存在
        user_work_dir = os.path.join(BASE_WORK_DIR, user_id)
        os.makedirs(user_work_dir, exist_ok=True)
    
    return _docker_containers[user_id]

def create_task_workspace(user_id: str, task_id: str) -> str:
    """为特定用户的任务创建工作空间
    
    Args:
        user_id: 用户ID，用于区分不同用户的工作空间
        task_id: 可选任务ID，如果不提供则自动生成
        
    Returns:
        str: 任务ID
    """
    global _task_directories
    
    # 确保用户任务映射表存在
    if user_id not in _task_directories:
        _task_directories[user_id] = {}
    
    # 创建用户特定的任务工作目录
    user_task_dir = os.path.join(BASE_WORK_DIR, user_id, task_id)
    os.makedirs(user_task_dir, exist_ok=True)
    
    # 记录用户任务目录
    _task_directories[user_id][task_id] = user_task_dir
    
    return user_task_dir

def execute_code_local(
    code: str,
    language: str,
    user_id: str,
    task_id: str
) -> str:
    """
    在本地环境中执行代码的函数
    
    Args:
        code: 要执行的代码
        language: 代码语言 ("python", "bash", "sh")
        user_id: 用户ID，区分不同用户
        task_id: 任务ID，如果不提供则创建新任务
        
    Returns:
        字符串结果，包含输出或错误信息
    """
    # 确保用户任务映射表存在
    if user_id not in _task_directories:
        _task_directories[user_id] = {}
    
    # 确保有任务ID和对应的工作目录
    if task_id not in _task_directories.get(user_id, {}):
        user_task_dir = create_task_workspace(user_id, task_id)
    
    task_dir = _task_directories[user_id][task_id]
    
    # 创建临时文件保存代码
    file_extension = ".py" if language == "python" else ".sh"
    with tempfile.NamedTemporaryFile(suffix=file_extension, dir=task_dir, delete=False) as temp_file:
        temp_file_path = temp_file.name
        temp_file.write(code.encode('utf-8'))
    
    # 设置执行命令
    if language == "python":
        command = f"python {temp_file_path}"
    elif language in ["bash", "sh"]:
        # 确保shell脚本有执行权限
        os.chmod(temp_file_path, 0o755)
        command = f"bash {temp_file_path}"
    else:
        return json.dumps({
            "user_id": user_id,
            "task_id": task_id,
            "success": False,
            "output": "",
            "error": f"不支持的语言: {language}",
            "working_directory": task_dir
        })
    
    # 执行命令
    try:
        # 切换到任务目录
        original_dir = os.getcwd()
        os.chdir(task_dir)
        
        # 执行代码
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        process = loop.run_until_complete(asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        ))
        stdout, stderr = loop.run_until_complete(process.communicate())
        loop.close()
        
        # 还原工作目录
        os.chdir(original_dir)
        
        # 清理临时文件
        os.unlink(temp_file_path)
        
        # 返回结果
        output = stdout.decode('utf-8')
        error = stderr.decode('utf-8')
        success = process.returncode == 0
        
        return json.dumps({
            "user_id": user_id,
            "task_id": task_id,
            "success": success,
            "output": output,
            "error": error,
            "working_directory": task_dir
        })
    
    except Exception as e:
        # 还原工作目录
        os.chdir(original_dir)
        
        # 清理临时文件
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        
        return json.dumps({
            "user_id": user_id,
            "task_id": task_id,
            "success": False,
            "output": "",
            "error": f"执行时发生错误: {str(e)}",
            "working_directory": task_dir
        })
    
def execute_code_docker(
    code: str,
    language: str,
    user_id: str,
    task_id: str
) -> str:
    """
    在Docker容器中执行代码的函数
    
    Args:
        code: 要执行的代码
        language: 代码语言 ("python", "bash", "sh")
        user_id: 用户ID，区分不同用户
        task_id: 任务ID，如果不提供则创建新任务
        
    Returns:
        字符串结果，包含输出或错误信息
    """
    # 确保用户任务映射表存在
    if user_id not in _task_directories:
        _task_directories[user_id] = {}
    
    # 确保有任务ID和对应的工作目录
    if task_id not in _task_directories.get(user_id, {}):
        user_task_dir = create_task_workspace(user_id, task_id)
    
    task_dir = _task_directories[user_id][task_id]
    
    # 获取用户专属的Docker容器
    container = get_docker_container(user_id=user_id)
    
    # 设置工作目录为当前任务目录
    print(f"user_id: {user_id}, task_id: {task_id}, task_dir: {task_dir}")
    container.set_work_dir(task_dir)
    
    # 执行代码
    result = container.execute(code, language)
    
    # 返回输出或错误 - 使用结构化JSON格式
    result_data = {
        "user_id": user_id,
        "task_id": task_id,
        "success": not result["error"],
        "output": result["output"] if not result["error"] else "",
        "error": result["error"] if result["error"] else "",
        "working_directory": task_dir
    }
    
    return json.dumps(result_data)

def execute_browser_task(
    task_description: str, 
    user_id: str, 
    task_id: str
) -> str:
    """
    执行浏览器任务并返回结果
    
    Args:
        task_description: 浏览器工作任务描述文本
        user_id: 用户ID，区分不同用户
        task_id: 任务ID，如果不提供则创建新任务
        
    Returns:
        str: JSON格式的任务执行结果
    """
    shell_code = f'python /app/agent_browser.py -t "{task_description}"'
    
    # 确保用户任务映射表存在
    if user_id not in _task_directories:
        _task_directories[user_id] = {}
    
    # 确保有任务ID和对应的工作目录
    if task_id not in _task_directories.get(user_id, {}):
        user_task_dir = create_task_workspace(user_id, task_id)
    
    task_dir = _task_directories[user_id][task_id]
    
    # 获取用户专属的Docker容器实例并执行命令
    container = get_docker_container(user_id=user_id)
    container.set_work_dir(task_dir)
    
    result = container.execute(shell_code, "bash")
    
    result_data = {
        "user_id": user_id,
        "task_id": task_id,
        "success": not result["error"],
        "output": result["output"] if not result["error"] else "",
        "error": result["error"] if result["error"] else "",
        "working_directory": task_dir
    }
    
    return json.dumps(result_data)

# 创建LlamaIndex工具
def create_code_executor_docker_tool():
    """创建docker代码执行工具"""
    return FunctionTool.from_defaults(
        name="docker_code_executor",
        description="在Docker容器中执行Python代码或Shell脚本。对于Python代码，使用language='python'；对于Shell脚本，使用language='bash'或'sh'。需要提供user_id区分不同用户，可以指定task_id继续在特定任务上下文中执行，不指定则创建新任务。",
        fn=execute_code_docker,
    )
 
def create_code_executor_local_tool():
    """创建本地代码执行工具"""
    return FunctionTool.from_defaults(
        name="local_code_executor",
        description="在本地环境中执行Python代码或Shell脚本。对于Python代码，使用language='python'；对于Shell脚本，使用language='bash'或'sh'。需要提供user_id区分不同用户，可以指定task_id继续在特定任务上下文中执行，不指定则创建新任务。",
        fn=execute_code_local,
    )

def create_browser_docker_tool():
    """创建浏览器执行工具"""
    return FunctionTool.from_defaults(
        name="browser_executor",
        description="执行浏览器相关任务，如搜索、浏览等。提供任务描述，工具将通过agent_browser.py执行相应操作。需要提供user_id区分不同用户。",
        fn=execute_browser_task,
    )

# 关闭特定用户的Docker容器
def close_docker_container(user_id: str = "default"):
    global _docker_containers
    if user_id in _docker_containers and _docker_containers[user_id]:
        _docker_containers[user_id].stop()
        _docker_containers[user_id] = None

# 关闭所有Docker容器
def close_all_docker_containers():
    global _docker_containers
    for user_id, container in _docker_containers.items():
        if container:
            container.stop()
    _docker_containers = {}

def test_docker_container():
    # Get container instance
    container = get_docker_container(user_id="test_user")
    
    # Test simple Python code
    code = """
import sys
print("Testing Docker container...")
print(f"Python version: {sys.version}")
"""
    
    try:
        # Execute code
        result = container.execute(code, "python")
        print("Execution result:")
        print(f"Output: {result['output']}")
    finally:
        # Cleanup
        close_docker_container("test_user")

# 测试代码
async def test_code_executor():

    tool = create_code_executor_docker_tool()
    
    try:
        user_id1 = "user1"
        user_id2 = "user2"
        
        # 测试用户1的Python代码 - 创建新任务
        python_code = """
print("Hello from Docker!")
import numpy as np
import json
print(f"Random 3x3 matrix:")
matrix = np.random.rand(3,3)
print(matrix)
print(f"Eigenvalues:")
print(np.linalg.eigvals(matrix))
with open("matrix_data.txt", "w") as f:
    f.write(str(matrix))
print("已将矩阵保存到文件")
"""
        result = tool(code=python_code, language="python", user_id=user_id1)
        result_data = json.loads(result.content)
        print("用户1 Python执行结果:")
        print(result_data)
        task_id1 = result_data["task_id"]
        
        # 测试用户2的Python代码 - 创建新任务
        python_code2 = """
print("Hello from User2!")
import os
import sys
print(f"Current directory: {os.getcwd()}")
print("Creating a user2 specific file...")
with open("user2_data.txt", "w") as f:
    f.write("This is user2's data")
print("File created successfully")
"""
        result = tool(code=python_code2, language="python", user_id=user_id2)
        result_data = json.loads(result.content)
        print("\n用户2 Python执行结果:")
        print(result_data)
        task_id2 = result_data["task_id"]
        
        # 用户1使用相同任务ID继续执行 - 应该能读取到之前的文件
        second_code = """
print("用户1读取之前保存的数据...")
with open("matrix_data.txt", "r") as f:
    data = f.read()
print(f"文件内容: {data}")
"""
        result = tool(code=second_code, language="python", user_id=user_id1, task_id=task_id1)
        result_data = json.loads(result.content)
        print("\n用户1继续执行结果:")
        print(result_data)
        
        # 用户2使用相同任务ID继续执行 - 应该能读取到之前的文件
        second_code2 = """
print("用户2读取之前保存的数据...")
with open("user2_data.txt", "r") as f:
    data = f.read()
print(f"文件内容: {data}")
"""
        result = tool(code=second_code2, language="python", user_id=user_id2, task_id=task_id2)
        result_data = json.loads(result.content)
        print("\n用户2继续执行结果:")
        print(result_data)
        
    finally:
        print("清理资源...")
        # 确保所有资源被清理
        close_all_docker_containers()

if __name__ == "__main__":
    asyncio.run(test_code_executor())