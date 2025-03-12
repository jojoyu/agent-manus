# Agent Manus

一个基于LLM的智能Agent系统，能够执行代码生成、代码执行、网页爬取等任务。

## 功能特点

- 支持多用户隔离
- 集成代码执行环境（Docker）
- 支持网页爬取
- 智能代码生成

## 快速开始

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 参考docker_image目录下build docker image
3. 运行程序：

```bash
python agent_main.py
```

## 使用说明

1. 启动程序后输入用户ID（可选）
2. 输入要执行的任务描述
3. 如需处理文件，输入文件名（文件应位于data目录下）
