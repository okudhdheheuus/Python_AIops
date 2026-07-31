# 构建阶段
FROM python:3.11-slim AS builder
WORKDIR /app
COPY backend/requirements.txt .
# 先装 CPU-only PyTorch，避免拉取带 CUDA 依赖的完整版（无 GPU 容器无法加载 CUDA 库）
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# 运行阶段
FROM python:3.11-slim
WORKDIR /app

# 从构建阶段复制全局安装的包（避免 /root/.local 权限问题）
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY backend/ ./backend/

# 非root用户运行（安全加固）
RUN useradd -m -u 1000 itops && chown -R itops:itops /app
USER itops

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
