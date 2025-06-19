import os

from typing import Dict, Any
from llama_index.core.tools import FunctionTool
from langchain_openai import ChatOpenAI
from llama_index.llms.langchain import LangChainLLM
from langchain_google_vertexai.model_garden import ChatAnthropicVertex
import logging

from prompts import CODE_GENERATION_PROMPT
from dotenv import load_dotenv
load_dotenv()

def get_model(model_name, **kwargs):
    """Get a model by name."""

    print(f"model: {model_name}")
    if model_name == "deepseek-v3":
        model = ChatOpenAI(
            model="deepseek-v3-cdp",
            temperature=0,
            max_tokens=8192,
            timeout=None,
            max_retries=2,
            api_key=os.getenv('DEEPSEEK_API_KEY'),
            base_url=os.getenv('API_BASE_URL'),
        )
    elif model_name.startswith("gpt-"):
        model = ChatOpenAI(
            model=model_name,
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=f'{os.environ["OPENAI_BASE_URL"]}',
        )
    elif model_name == "claude-opus-4":
        model = ChatAnthropicVertex(
            model=os.environ["CLAUDE_MODEL_NAME"], 
            temperature=0,
            max_tokens=8192,
            max_retries=6,
            stop=None,
            project=os.environ["GCP_PROJECT"], 
            location=os.environ["GCP_LOCATION"]
        )
    else:
        raise ValueError
    
    return model

def create_code_generator_tool(
    model_name: str = "gpt-4o"
) -> FunctionTool:
    """创建代码生成工具"""
    
    def generate_python_code(
        task_description: str,
        user_id: str = "default",
        task_id: str = None,
        additional_context: str = ""
    ) -> str:
        """
        根据任务描述生成Python代码
        
        Args:
            task_description (str): 任务描述
            user_id (str): 用户ID
            task_id (str): 任务ID
            additional_context (str): 额外的上下文信息
            
        Returns:
            str: 生成的Python代码
        """
        llm = LangChainLLM(llm=get_model(model_name))
        
        prompt = f"""{CODE_GENERATION_PROMPT}

用户ID: {user_id}
任务ID: {task_id}
任务描述：{task_description}
额外上下文：{additional_context}

请直接返回代码，无需其他解释。
"""
        
        response = llm.complete(prompt)
        return response.text.strip()

    return FunctionTool.from_defaults(
        fn=generate_python_code,
        name="code_generator",
        description="根据任务描述生成Python代码的工具。需要提供user_id和task_id，返回可执行的Python代码字符串。"
    )
