import os
import tempfile
import docker
import uuid
from typing import Dict, Optional

class DockerContainer:
    """管理Docker容器的简单类"""
    def __init__(
        self,
        image: str = "python-data-analysis:3.11",
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
                print(f"使用现有容器 {self.container_name}")
            except docker.errors.NotFound:
                # 如果不存在则创建新容器
                self.container = client.containers.run(
                    self.image,
                    command="tail -f /dev/null", # 保持容器运行
                    detach=True,
                    working_dir=self.base_work_dir,
                    name=self.container_name,
                    auto_remove=self.auto_remove,
                    volumes={self.base_work_dir: {'bind': self.base_work_dir, 'mode': 'rw'}}
                )
                print(f"创建新容器 {self.container_name}")
        except Exception as e:
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
