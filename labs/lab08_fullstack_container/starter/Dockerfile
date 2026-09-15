# Lab08 starter: 后端最小镜像（教学起手骨架）
# 构建上下文是你自己的后端项目目录，至少包含 requirements.txt 与 src/
FROM python:3.12-slim
WORKDIR /app

# 依赖层：清单数周才变，安装结果可长期命中缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 代码层：业务代码每天在变，只让这一层失效
COPY src/ ./src/

ENV PYTHONPATH=/app/src
ENV DOCSEARCH_DATA_DIR=/data
RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "docsearch.main:app", "--host", "0.0.0.0", "--port", "8000"]
