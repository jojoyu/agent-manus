import os
import tempfile
import docker
import uuid
import time
import traceback
from typing import Dict, Optional

from dotenv import load_dotenv
load_dotenv()

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
    container = DockerContainer(container_name='llamaindex-executor-default', auto_remove=False)
    try:
        # 测试容器启动
        container.start()
        print("容器启动测试成功")
        container.set_work_dir("/Users/pingcy/workspace/tasks/default/TASK-557c26c1")

        # 测试Python代码执行
        python_code = '''print('Hello from Python!')
import os
print(os.getcwd())'''
        result = container.execute(python_code)
        print("Python执行结果:", result)
  
        # 测试Shell脚本执行
        shell_code = '''#!/bin/bash
echo "Hello from Bash!"
ls -l'''
        result = container.execute(shell_code, language="sh")
        print("Shell执行结果:", result)

        # 测试Shell脚本执行
        python_code = 'import pandas as pd\nimport matplotlib.pyplot as plt\nimport matplotlib as mpl\nimport os\nfrom openai import OpenAI\n\n# 设置matplotlib中文字体\nmpl.rcParams[\'font.sans-serif\'] = [\'WenQuanYi Zen Hei\', \'SimHei\']\nmpl.rcParams[\'axes.unicode_minus\'] = False\n\n# 初始化OpenAI客户端\nclient = OpenAI()\n\ndef load_data():\n    """加载游戏模式数据"""\n    try:\n        # 使用正确的文件路径\n        df = pd.read_csv("/Users/pingcy/workspace/tasks/default/TASK-557c26c1/2.csv")\n        # 验证必要列是否存在\n        required_columns = [\'统计日期\', \'模式名称\', \'年龄\', \'社交玩法标签\', \'人均参与次数\', \'人数\']\n        if not all(col in df.columns for col in required_columns):\n            raise ValueError("数据文件缺少必要的列")\n        return df\n    except FileNotFoundError:\n        raise FileNotFoundError("未找到数据文件")\n    except Exception as e:\n        raise Exception(f"加载数据时出错: {str(e)}")\n\ndef plot_key_metrics_distribution(df):\n    """绘制关键指标分布图"""\n    try:\n        fig, axes = plt.subplots(2, 1, figsize=(10, 8))\n        \n        # 人均参与次数分布\n        df[\'人均参与次数\'].plot(kind=\'hist\', bins=20, ax=axes[0], color=\'skyblue\', edgecolor=\'black\')\n        axes[0].set_title(\'人均参与次数分布\')\n        axes[0].set_xlabel(\'人均参与次数\')\n        axes[0].set_ylabel(\'频数\')\n        \n        # 人数分布\n        df[\'人数\'].plot(kind=\'hist\', bins=20, ax=axes[1], color=\'lightgreen\', edgecolor=\'black\')\n        axes[1].set_title(\'人数分布\')\n        axes[1].set_xlabel(\'人数\')\n        axes[1].set_ylabel(\'频数\')\n        \n        plt.tight_layout()\n        plt.savefig(\'key_metrics_distribution.png\')\n        plt.close()\n    except Exception as e:\n        raise Exception(f"绘制关键指标分布图时出错: {str(e)}")\n\ndef plot_dimension_comparison(df):\n    """绘制不同维度对比图"""\n    try:\n        # 年龄组对比\n        age_group = df.groupby(\'年龄\')[\'人均参与次数\'].mean().sort_values()\n        plt.figure(figsize=(8, 5))\n        age_group.plot(kind=\'bar\', color=\'orange\')\n        plt.title(\'不同年龄组人均参与次数对比\')\n        plt.xlabel(\'年龄组\')\n        plt.ylabel(\'平均人均参与次数\')\n        plt.xticks(rotation=45)\n        plt.tight_layout()\n        plt.savefig(\'age_group_comparison.png\')\n        plt.close()\n        \n        # 社交玩法标签对比\n        social_tag = df.groupby(\'社交玩法标签\')[\'人均参与次数\'].mean().sort_values()\n        plt.figure(figsize=(8, 5))\n        social_tag.plot(kind=\'bar\', color=\'purple\')\n        plt.title(\'不同社交玩法标签人均参与次数对比\')\n        plt.xlabel(\'社交玩法标签\')\n        plt.ylabel(\'平均人均参与次数\')\n        plt.xticks(rotation=45)\n        plt.tight_layout()\n        plt.savefig(\'social_tag_comparison.png\')\n        plt.close()\n    except Exception as e:\n        raise Exception(f"绘制维度对比图时出错: {str(e)}")\n\ndef create_pivot_table(df):\n    """创建多维钻取透视表"""\n    try:\n        # 日期x模式x年龄组透视表\n        pivot = pd.pivot_table(df, \n                              values=[\'人均参与次数\', \'人数\'],\n                              index=[\'统计日期\', \'模式名称\', \'年龄\'],\n                              aggfunc={\'人均参与次数\': \'mean\', \'人数\': \'sum\'})\n        \n        # 保存透视表到Excel\n        with pd.ExcelWriter(\'game_mode_analysis.xlsx\') as writer:\n            pivot.to_excel(writer, sheet_name=\'多维钻取\')\n            \n            # 创建汇总透视表\n            summary_pivot = pd.pivot_table(df,\n                                         values=[\'人均参与次数\', \'人数\'],\n                                         index=[\'模式名称\'],\n                                         columns=[\'年龄\', \'社交玩法标签\'],\n                                         aggfunc={\'人均参与次数\': \'mean\', \'人数\': \'sum\'},\n                                         fill_value=0)\n            summary_pivot.to_excel(writer, sheet_name=\'汇总透视表\')\n    except Exception as e:\n        raise Exception(f"创建透视表时出错: {str(e)}")\n\ndef main():\n    try:\n        # 加载数据\n        df = load_data()\n        \n        # 1. 关键指标分布图\n        plot_key_metrics_distribution(df)\n        \n        # 2. 不同维度对比\n        plot_dimension_comparison(df)\n        \n        # 3. 多维钻取透视表\n        create_pivot_table(df)\n        \n        print("分析完成，结果已保存到当前目录")\n    except Exception as e:\n        print(f"执行过程中出错: {str(e)}")\n        exit(1)\n\nif __name__ == "__main__":\n    main()'       
        result = container.execute(python_code)
        print("Python执行结果:", result)

    finally:
        container.stop()
