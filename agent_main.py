from typing import List, Dict
import uuid
from llama_index.core.agent import ReActAgent,FunctionCallingAgent
from llama_index.core.tools import ToolOutput
from llama_index.llms.openai import OpenAI
from langchain_openai import ChatOpenAI
from llama_index.llms.langchain import LangChainLLM
from llama_index.llms.ollama import Ollama
import asyncio
from tool_code_executor import create_task_workspace
from tool_code_executor import create_code_executor_docker_tool,create_code_executor_local_tool,close_docker_container,create_browser_docker_tool
from tool_code_generator import create_code_generator_tool
from tool_webpage_crawler import create_webpage_crawler_tool
from llama_index.core.llms import ChatMessage
from llama_index.llms.openai_like import OpenAILike
from llama_index.llms.openllm import OpenLLM
from prompts import REACT_AGENT_CONTEXT,DEFAULT_INITIAL_PLAN_PROMPT,DEFAULT_PLAN_REFINE_PROMPT
from llama_index.core.agent import (
    StructuredPlannerAgent,
    FunctionCallingAgentWorker,
    ReActAgentWorker,
)
import shutil
import os

# 全局变量 - Agent映射表（按用户ID组织）
_agents: Dict[str, ReActAgent] = {}

def generate_task_id():
    """生成一个TASK开头的唯一ID"""
    return f"TASK-{str(uuid.uuid4())[:8]}"

def get_agent(
    user_id: str = "default",
    llm = None
) -> ReActAgent:
    
    """获取或创建用户专属的Agent实例"""
    global _agents
    
    if user_id not in _agents:

        # 如果没有提供LLM，创建默认的LLM
        if llm is None:
            llm = LangChainLLM(llm=ChatOpenAI(model="doubao-1.5-256k"))
        
        # 创建用户专属的工具实例
        tool_code_executor_docker = create_code_executor_docker_tool()
        tool_browser_docker = create_browser_docker_tool()
        tool_code_generator = create_code_generator_tool()
        tool_webpage_crawler = create_webpage_crawler_tool()  # 新增网页采集工具
        
        # 创建用户专属的Agent
        
        _agents[user_id] = ReActAgent.from_tools(
            max_iterations=20,
            tools=[
                tool_code_generator,
                tool_code_executor_docker, 
                tool_browser_docker,
                tool_webpage_crawler  # 添加到工具列表
            ],
            llm=llm,
            verbose=True,
            context=REACT_AGENT_CONTEXT
        )
    
    return _agents[user_id]

def close_agent(user_id: str = "default"):
    """关闭特定用户的Agent和相关资源"""
    global _agents
    if user_id in _agents:
        # 关闭该用户的Docker容器
        close_docker_container(user_id)
        # 移除Agent实例
        del _agents[user_id]

def close_all_agents():
    """关闭所有用户的Agent和相关资源"""
    global _agents
    # 获取所有用户ID的副本
    user_ids = list(_agents.keys())
    # 逐个关闭用户的Agent和资源
    for user_id in user_ids:
        close_agent(user_id)

async def test_react_agent():
    try:
        print("欢迎使用Awesome Manus! 输入'exit'或'quit'退出程序。")
        
        # 获取用户ID
        user_id = input("\n请输入用户ID (直接回车使用default): ").strip()
        if not user_id:
            user_id = "default"

        while True:
            # 获取用户输入的任务
            query = input("\n请输入要执行的任务: ")
            
            # 检查是否退出
            if query.lower() in ['exit', 'quit']:
                print("程序已退出")
                break
            
            if not query.strip():
                continue
            
            # 获取用户输入的文件名
            filename = input("\n请输入要处理的文件名 (位于data目录下): ").strip()

            # 获取或创建用户专属的Agent
            agent = get_agent(user_id)

            # 生成task_id并组装任务
            task_id = generate_task_id()
            
            # 创建工作目录
            workspace_path = create_task_workspace(user_id, task_id)

            if filename:

                # 检查文件是否存在
                source_path = os.path.join(workspace_path, '../data', filename)
                print(f"source_path: {source_path}")
                if not os.path.exists(source_path):
                    print(f"错误：文件 {filename} 不存在于data目录中")
                    continue
                
                # 拷贝文件到工作目录
                target_path = os.path.join(workspace_path, filename)
                shutil.copy2(source_path, target_path)

            else:
                target_path = None
                
            task_input = {
                "user_id": user_id,
                "task_id": task_id,
                "task": query.strip(),
                "target_file": target_path
            }
            
            # 使用非流式响应
            response = await agent.achat(str(task_input))
            print(f"任务执行结果: {response}")

    finally:
        # 确保所有资源被清理
        close_all_agents()

if __name__ == "__main__":
    asyncio.run(test_react_agent())