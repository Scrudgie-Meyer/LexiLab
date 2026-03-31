FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# встановити Rust
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain stable
ENV PATH="/root/.cargo/bin:${PATH}"

# встановити Python залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt maturin

# зібрати Rust модуль
COPY rust_module ./rust_module
RUN cd rust_module \
    && rm -rf target/wheels \
    && maturin build --release --interpreter python \
    && pip install target/wheels/*.whl

# скопіювати решту коду
COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
