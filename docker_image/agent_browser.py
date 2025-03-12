from langchain_openai import ChatOpenAI
from browser_use import Agent
from dotenv import load_dotenv
from browser_use import Agent, Browser, BrowserConfig
from browser_use.browser.context import BrowserContextConfig
from pydantic import SecretStr
import argparse
import asyncio

# 加载环境变量
load_dotenv()

# 定义可用的LLM模型
LLM_MODELS = {
    "gpt-4o-mini": ChatOpenAI(model="gpt-4o-mini"),
    "moonshot": ChatOpenAI(model='moonshot-v1-32k'),
    "doubao": ChatOpenAI(model='doubao-1.5-32k'),
}

# 默认浏览器配置
browser_config = BrowserConfig(
)

async def run_browser_agent(task, model_name="gpt4o-mini", use_vision=True, max_failures=2, max_actions=3):
    """运行浏览器代理执行指定任务"""
    # 获取对应的LLM模型
    if model_name not in LLM_MODELS:
        print(f"错误：未找到模型 '{model_name}'。可用模型: {', '.join(LLM_MODELS.keys())}")
        return
    
    llm = LLM_MODELS[model_name]
    
    # 初始化浏览器
    browser = Browser(config=browser_config)
    
    try:
        # 创建代理
        agent = Agent(
            task=task,
            llm=llm,
            use_vision=use_vision,
            max_failures=max_failures,
            max_actions_per_step=max_actions,
            browser=browser
        )
        
        # 运行代理
        result = await agent.run()
        print(f"\n任务结果:\n{result.final_result()}\n")
        return result.final_result()
    
    finally:
        # 确保浏览器关闭
        await browser.close()

async def main():
    """主函数，处理命令行参数并运行代理"""
    # 创建参数解析器
    parser = argparse.ArgumentParser(description='浏览器自动化代理')
    parser.add_argument('--task', '-t', type=str, help='要执行的任务描述', required=False,
                       default="google搜索deepseek，获取第一个链接")
    parser.add_argument('--model', '-m', type=str, choices=LLM_MODELS.keys(),
                       default='gpt-4o-mini', help='使用的LLM模型')
    parser.add_argument('--no-vision', action='store_false', dest='vision',
                       help='禁用视觉功能')
    parser.add_argument('--max-failures', type=int, default=2,
                       help='最大失败次数')
    parser.add_argument('--max-actions', type=int, default=3,
                       help='每个步骤的最大操作数')
    
    # 解析参数
    args = parser.parse_args()
    
    # 显示任务信息
    print(f"\n执行任务: '{args.task}'")
    print(f"使用模型: {args.model}")
    print(f"视觉功能: {'启用' if args.vision else '禁用'}")
    print(f"最大失败次数: {args.max_failures}")
    print(f"每步最大操作数: {args.max_actions}\n")
    
    # 运行代理
    await run_browser_agent(
        task=args.task,
        model_name=args.model,
        use_vision=args.vision,
        max_failures=args.max_failures,
        max_actions=args.max_actions
    )

# 如果直接运行此脚本
if __name__ == "__main__":
    asyncio.run(main())