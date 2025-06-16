import os
import tempfile
import docker
import uuid
import time
import traceback
from typing import Dict, Optional

class DockerContainer:
    """管理Docker容器的简单类"""
    def __init__(
        self,
        image: str = "python_code_executor:3.11",
        container_name: str = "llamaindex-executor",
        base_work_dir: str = "/Users/pingcy/workspace",
        auto_remove: bool = True
    ):
        self.image = image
        self.container_name = container_name
        self.base_work_dir = base_work_dir
        self.auto_remove = auto_remove
        self.container = None
        self.current_work_dir = base_work_dir
        
    def start(self):
        """启动Docker容器"""
        client = docker.from_env()
        
        try:
            # 尝试获取现有容器
            try:
                self.container = client.containers.get(self.container_name)
                if self.container.status != 'running':
                    print(f"重启容器 {self.container_name}")
                    self.container.start()
                else:
                    print(f"使用运行中容器 {self.container_name}")
            except docker.errors.NotFound:
                # 创建新容器时增加超时和重试机制
                self.container = client.containers.run(
                    self.image,
                    command="tail -f /dev/null", # 保持容器运行
                    detach=True,
                    working_dir=self.base_work_dir,
                    name=self.container_name,
                    auto_remove=self.auto_remove,
                    volumes={self.base_work_dir: {'bind': self.base_work_dir, 'mode': 'rw'}},
                    healthcheck={
                        'test': ['CMD-SHELL', 'echo ready'],
                        'interval': 1000000000
                    },
                    environment={
                        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY', ''),
                        'OPENAI_BASE_URL': os.getenv('OPENAI_BASE_URL', '')
                    }
                )
                print(f"创建新容器 {self.container_name}")
                
                # 等待容器健康状态
                for _ in range(10):
                    self.container.reload()
                    if self.container.attrs['State']['Health']['Status'] == 'healthy':
                        break
                    time.sleep(1)
                else:
                    raise RuntimeError("容器启动超时")
        except Exception as e:
            print(f"容器操作失败详情:\n{traceback.format_exc()}")
            raise RuntimeError(f"启动Docker容器失败: {str(e)}")
            
        return self
    
    def set_work_dir(self, work_dir: str) -> None:
        """设置当前工作目录
        
        Args:
            work_dir: 新的工作目录
        """
        self.current_work_dir = work_dir
        # 确保工作目录存在
        os.makedirs(work_dir, exist_ok=True)
        # 在容器中也创建目录
        if self.container:
            self.container.exec_run(f"mkdir -p {work_dir}")
        
    def stop(self):
        """停止Docker容器"""
        if self.container and self.auto_remove:
            print(f"停止容器 {self.container_name}")
            self.container.stop()
            self.container = None
            
    def execute(self, code: str, language: str = "python", work_dir: Optional[str] = None) -> Dict[str, str]:
        """在Docker容器中执行代码
        
        Args:
            code: 要执行的代码
            language: 代码语言，支持 "python", "sh", "bash"
            work_dir: 执行代码的工作目录，如果不提供则使用当前工作目录
            
        Returns:
            Dict包含output和error字段
        """
        if not self.container:
            self.start()
        
        # 使用指定工作目录或当前工作目录
        execution_dir = work_dir if work_dir else self.current_work_dir
        
        result = {"output": "", "error": ""}
        temp_file = None
        
        try:
            # 根据语言选择文件后缀和执行命令
            file_suffix = ".py" if language == "python" else ".sh"
            
            #取出多余的md符号，比如```python,或者```shell，或者```bash，或者```sh，或者```
            code = code.replace("```python", "").replace("```shell", "").replace("```bash", "").replace("```sh", "").replace("```", "")
            
            # 将代码写入临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix=file_suffix, dir=execution_dir, delete=False) as f:
                f.write(code)
                temp_file = f.name
                
            if language == "python":
                execute_cmd = f"python {temp_file}"
            else:
                # 为shell脚本添加执行权限
                os.chmod(temp_file, 0o755)
                execute_cmd = f"bash {temp_file}"
                
            # 在容器中执行代码
            exit_code, output = self.container.exec_run(
                execute_cmd,
                workdir=execution_dir
            )
            
            output_str = output.decode('utf-8')
            
            if exit_code != 0:
                result["error"] = output_str
            else:
                if output_str:
                    result["output"] = output_str
                else:
                    result["output"] = "代码执行成功"
                
        except Exception as e:
            result["error"] = str(e)
            
        finally:
            # 清理临时文件
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)
        
        return result


if __name__ == '__main__':
    def convert_to_escaped_string(code):
        # 转义单引号和反斜杠
        escaped_code = code.replace('\\', '\\\\').replace("'", "\\'")
        # 替换换行符为\n字面量
        return "'" + escaped_code.replace('\n', '\\n') + "'"

    # 测试容器启动和代码执行
    container = DockerContainer(auto_remove=False)
    try:
        # 测试容器启动
        container.start()
        print("容器启动测试成功")
        
        # 测试Python代码执行
        python_code1 = '''print('Hello from Python!')
import os
print(os.getcwd())'''
        result = container.execute(python_code1)
        print("Python执行结果:", result)
  
        # 测试Shell脚本执行
        shell_code = '''#!/bin/bash
echo "Hello from Bash!"
ls -l'''
        result = container.execute(shell_code, language="sh")
        print("Shell执行结果:", result)

        # 测试Python代码执行
        python_code = '''
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import traceback
import os
from openai import OpenAI

# Set matplotlib Chinese font for container execution
plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

def analyze_csv(file_path):
    try:
        # Read CSV file
        df = pd.read_csv(file_path)
        
        # Data exploration
        print("Data Overview:")
        print(df.head())
        print("\nData Summary:")
        print(df.describe())
        print("\nMissing Values:")
        print(df.isnull().sum())

        # Distribution plots
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            for col in numeric_cols:
                plt.figure(figsize=(8, 6))
                df[col].hist(bins=20)
                plt.title(f'Distribution of {col}')
                plt.xlabel(col)
                plt.ylabel('Frequency')
                plt.savefig(f'{col}_distribution.png')
                plt.close()
                print(f"\nSaved distribution plot for {col}")

        # Comparison charts
        if len(numeric_cols) >= 2:
            plt.figure(figsize=(10, 6))
            df[numeric_cols[:2]].boxplot()
            plt.title('Comparison of first two numeric columns')
            plt.savefig('numeric_comparison.png')
            plt.close()
            print("\nSaved numeric comparison plot")

        # Pivot tables
        categorical_cols = df.select_dtypes(include=['object']).columns
        if len(categorical_cols) > 0 and len(numeric_cols) > 0:
            pivot = pd.pivot_table(df, 
                                 index=categorical_cols[0], 
                                 values=numeric_cols[0], 
                                 aggfunc='mean')
            print("\nPivot Table:")
            print(pivot)

        # Generate pyramid principle analysis using GPT-4o
        client = OpenAI()
        
        prompt = f"""Perform a pyramid principle analysis on this dataset:
        {df.head().to_string()}
        
        Key findings:
        1. 
        2. 
        3. 
        
        Recommendations:
        1. 
        2. 
        3."""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a data analysis assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        
        print("\nPyramid Principle Analysis:")
        print(response.choices[0].message.content)

    except Exception as e:
        print(f"Error occurred: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    target_file = '/Users/pingcy/workspace/tasks/default/TASK-efd8d0bf/2.csv'
    if os.path.exists(target_file):
        analyze_csv(target_file)
    else:
        print(f"Error: File not found at {target_file}")
'''

        container.set_work_dir("/Users/pingcy/workspace/tasks/default/TASK-efd8d0bf")
        python_code = 'import pandas as pd\nimport numpy as np\nimport matplotlib.pyplot as plt\nimport traceback\nimport os\nfrom openai import OpenAI\n\n# Set matplotlib Chinese font for container execution\nplt.rcParams[\'font.sans-serif\'] = [\'WenQuanYi Zen Hei\', \'SimHei\']\nplt.rcParams[\'axes.unicode_minus\'] = False\n\ndef analyze_csv(file_path):\n    try:\n        # Read CSV file\n        df = pd.read_csv(file_path)\n        \n        # Data exploration\n        print("Data Overview:")\n        print(df.head())\n        print("\\nData Summary:")\n        print(df.describe())\n        print("\\nMissing Values:")\n        print(df.isnull().sum())\n\n        # Distribution plots\n        numeric_cols = df.select_dtypes(include=[np.number]).columns\n        if len(numeric_cols) > 0:\n            for col in numeric_cols:\n                plt.figure(figsize=(8, 6))\n                df[col].hist(bins=20)\n                plt.title(f\'Distribution of {col}\')\n                plt.xlabel(col)\n                plt.ylabel(\'Frequency\')\n                plt.savefig(f\'{col}_distribution.png\')\n                plt.close()\n                print(f"\\nSaved distribution plot for {col}")\n\n        # Comparison charts\n        if len(numeric_cols) >= 2:\n            plt.figure(figsize=(10, 6))\n            df[numeric_cols[:2]].boxplot()\n            plt.title(\'Comparison of first two numeric columns\')\n            plt.savefig(\'numeric_comparison.png\')\n            plt.close()\n            print("\\nSaved numeric comparison plot")\n\n        # Pivot tables\n        categorical_cols = df.select_dtypes(include=[\'object\']).columns\n        if len(categorical_cols) > 0 and len(numeric_cols) > 0:\n            pivot = pd.pivot_table(df, \n                                 index=categorical_cols[0], \n                                 values=numeric_cols[0], \n                                 aggfunc=\'mean\')\n            print("\\nPivot Table:")\n            print(pivot)\n\n        # Generate pyramid principle analysis using GPT-4o\n        client = OpenAI()\n        \n        prompt = f"""Perform a pyramid principle analysis on this dataset:\n        {df.head().to_string()}\n        \n        Key findings:\n        1. \n        2. \n        3. \n        \n        Recommendations:\n        1. \n        2. \n        3."""\n        \n        response = client.chat.completions.create(\n            model="gpt-4o",\n            messages=[\n                {"role": "system", "content": "You are a data analysis assistant."},\n                {"role": "user", "content": prompt}\n            ]\n        )\n        \n        print("\\nPyramid Principle Analysis:")\n        print(response.choices[0].message.content)\n\n    except Exception as e:\n        print(f"Error occurred: {e}")\n        print(traceback.format_exc())\n\nif __name__ == "__main__":\n    target_file = \'/Users/pingcy/workspace/tasks/default/TASK-efd8d0bf/2.csv\'\n    if os.path.exists(target_file):\n        analyze_csv(target_file)\n    else:\n        print(f"Error: File not found at {target_file}")'
        result = container.execute(python_code)
        print("Python执行结果:", result)

    finally:
        container.stop()
