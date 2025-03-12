import os
from typing import Optional
from llama_index.core.tools import FunctionTool
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse

BASE_WORK_DIR = "/Users/pingcy/workspace/tasks"

def create_webpage_crawler_tool() -> FunctionTool:
    """创建网页内容采集工具"""
    
    def crawl_webpage(
        url: str,
        user_id: str = "default",
        task_id: Optional[str] = None
    ) -> str:
        """
        采集网页内容并保存为文本文件
        
        Args:
            url (str): 网页链接
            user_id (str): 用户ID
            task_id (str): 任务ID
            
        Returns:
            str: 保存的文件完整路径
        """
        try:
            # 发送请求获取网页内容
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            # 使用BeautifulSoup解析内容
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 清理网页内容
            # 1. 移除非核心内容标签
            for element in soup(['script', 'style', 'noscript', 'iframe', 'head', 
                              'header', 'footer', 'nav', 'sidebar', 'comments',
                              'aside', 'advertisement']):
                element.decompose()
                
            # 2. 尝试提取文章主体内容
            main_content = None
            for tag in ['article', 'main', '[role="main"]', '.main-content', '#content']:
                main_content = soup.select_one(tag)
                if main_content:
                    break
                    
            # 3. 提取和清理文本
            if main_content:
                text = main_content.get_text()
            else:
                # 如果找不到主体内容标签，则提取所有<p>标签内容
                paragraphs = soup.find_all('p')
                text = '\n'.join(p.get_text() for p in paragraphs)
                
            # 4. 整理文本格式
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk and len(chunk) > 20)
            
            # 5. 移除多余空行和特殊字符
            text = re.sub(r'\n\s*\n', '\n\n', text)
            text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
            
            # 创建保存目录
            domain = urlparse(url).netloc
            save_dir = os.path.join(
                BASE_WORK_DIR,
                user_id,
                task_id if task_id else "",
                "crawled_pages"
            )
            os.makedirs(save_dir, exist_ok=True)
            
            # 生成文件名并保存
            filename = f"{domain}_{task_id}.txt" if task_id else f"{domain}.txt"
            file_path = os.path.join(save_dir, filename)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"Source URL: {url}\n\n")
                f.write(text)
            
            return file_path
            
        except Exception as e:
            raise Exception(f"Failed to crawl webpage: {str(e)}")

    return FunctionTool.from_defaults(
        fn=crawl_webpage,
        name="webpage_crawler",
        description="采集指定网页的内容,清洗后保存为文本文件。需要提供url、user_id和task_id。返回保存的文件路径。"
    )
