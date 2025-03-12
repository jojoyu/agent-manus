#!/bin/bash
# Docker镜像构建脚本

# 默认值
IMAGE_NAME="python_code_executor"
TAG="3.11"
DOCKERFILE="./Dockerfile"
OPENAI_API_KEY=""
OPENAI_API_BASE=""

# 输出帮助信息
show_help() {
  echo "用法: ./build.sh [选项]"
  echo ""
  echo "选项:"
  echo "  -n, --name NAME          指定镜像名称 (默认: $IMAGE_NAME)"
  echo "  -t, --tag TAG            指定镜像标签 (默认: $TAG)"
  echo "  -f, --file FILE          指定Dockerfile路径 (默认: $DOCKERFILE)"
  echo "  --openai-api-key KEY     指定OpenAI API密钥"
  echo "  --openai-api-base URL    指定OpenAI API基础URL"
  echo "  --no-cache               构建时不使用缓存"
  echo "  --pull                   构建前拉取最新的基础镜像"
  echo "  -h, --help               显示帮助信息"
  echo ""
  echo "示例:"
  echo "  ./build.sh --name data-science --tag latest --file ./custom.Dockerfile"
}

# 解析命令行参数
PARAMS=""
NO_CACHE=""
PULL=""

while (( "$#" )); do
  case "$1" in
    -n|--name)
      if [ -n "$2" ] && [ ${2:0:1} != "-" ]; then
        IMAGE_NAME=$2
        shift 2
      else
        echo "错误: 参数 $1 需要一个值" >&2
        exit 1
      fi
      ;;
    -t|--tag)
      if [ -n "$2" ] && [ ${2:0:1} != "-" ]; then
        TAG=$2
        shift 2
      else
        echo "错误: 参数 $1 需要一个值" >&2
        exit 1
      fi
      ;;
    -f|--file)
      if [ -n "$2" ] && [ ${2:0:1} != "-" ]; then
        DOCKERFILE=$2
        shift 2
      else
        echo "错误: 参数 $1 需要一个值" >&2
        exit 1
      fi
      ;;
    --openai-api-key)
      if [ -n "$2" ] && [ ${2:0:1} != "-" ]; then
        OPENAI_API_KEY=$2
        shift 2
      else
        echo "错误: 参数 $1 需要一个值" >&2
        exit 1
      fi
      ;;
    --openai-api-base)
      if [ -n "$2" ] && [ ${2:0:1} != "-" ]; then
        OPENAI_API_BASE=$2
        shift 2
      else
        echo "错误: 参数 $1 需要一个值" >&2
        exit 1
      fi
      ;;
    --no-cache)
      NO_CACHE="--no-cache"
      shift
      ;;
    --pull)
      PULL="--pull"
      shift
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    --) # 结束参数解析
      shift
      break
      ;;
    -*|--*=) # 未知选项
      echo "错误: 未知选项 $1" >&2
      exit 1
      ;;
    *) # 保留额外参数
      PARAMS="$PARAMS $1"
      shift
      ;;
  esac
done

# 检查Dockerfile是否存在
if [ ! -f "$DOCKERFILE" ]; then
  echo "错误: Dockerfile '$DOCKERFILE' 不存在"
  exit 1
fi

# 设置参数
eval set -- "$PARAMS"

# 显示构建信息
echo "=========================================="
echo "开始构建Docker镜像"
echo "镜像名称: $IMAGE_NAME"
echo "镜像标签: $TAG"
echo "Dockerfile: $DOCKERFILE"
echo "=========================================="

# 使用docker命令直接构建
docker build -t "$IMAGE_NAME:$TAG" -f "$DOCKERFILE" $NO_CACHE $PULL \
  --build-arg OPENAI_API_KEY="$OPENAI_API_KEY" \
  --build-arg OPENAI_API_BASE="$OPENAI_API_BASE" \
  --build-arg OPENAI_BASE_URL="$OPENAI_API_BASE" .

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  echo "=========================================="
  echo "镜像构建成功: $IMAGE_NAME:$TAG"
  echo "=========================================="
else
  echo "=========================================="
  echo "镜像构建失败"
  echo "=========================================="
  exit $EXIT_CODE
fi