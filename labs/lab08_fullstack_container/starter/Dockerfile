# Lab08 starter: 后端最小镜像（教学起手骨架）
# 构建上下文是你自己的后端项目目录，至少包含 pyproject.toml、uv.lock 与 src/
FROM python:3.12-slim
WORKDIR /app

# 依赖层：清单与锁文件数周才变，安装结果可长期命中缓存
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev --no-install-project

# 代码层：业务代码每天在变，只让这一层失效
COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH"
ENV DOCSEARCH_DATA_DIR=/data
RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "docsearch.main:app", "--host", "0.0.0.0", "--port", "8000"]
