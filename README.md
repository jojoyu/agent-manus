# Agent Manus

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Required-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

一个基于LLM的多用户智能Agent演示系统，能够在动态启动的容器中执行代码、脚本、网络自动化浏览等工具，以完成输入任务。

## 🚀 功能特点

- 🔒 支持多用户隔离
- 🐳 集成代码执行环境（Docker）
- 🌐 支持自动化网络浏览
- 💻 智能代码生成与执行
- 🛠️ 可扩展的工具系统

## 🔧 环境要求

- Python 3.9+
- Docker
- 操作系统：Linux/MacOS/Windows

## 🏃‍♂️ 快速开始

1. 克隆项目：

```bash
git clone https://github.com/pingcy/agent-manus.git
cd agent-manus
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 构建Docker镜像：

```bash
cd docker_image
sh build.sh
```

4. 运行程序：

```bash
python agent_main.py
```

## 📖 使用说明

1. 启动程序后输入用户ID（可选）
2. 输入要执行的任务描述
3. 如需处理文件，输入文件名（文件应位于用户目录下的data目录下）

## 🎯 代码说明

参考微信公众号文章：

![使用示例](image/README/1741773352264.jpg)

## 📝 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！
