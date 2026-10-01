FROM python:3.12-slim

# tesseract-ocr-por e o que da precisao em texto acentuado; poppler-utils traz
# pdftotext (preserva colunas) e pdftoppm (renderiza PDF-imagem para o OCR).
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-por poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Dependencias primeiro, numa camada propria: mudar o codigo nao reinstala tudo.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --all-extras --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --all-extras --no-dev

# Roda sem privilegio: o servico parseia arquivo de terceiros e chama
# pdftotext, pdftoppm e tesseract como subprocesso. Root aqui transformaria uma
# falha em qualquer um deles em comprometimento do container.
RUN useradd --system --no-create-home --uid 10001 nfscan \
    && chown -R nfscan:nfscan /app
USER nfscan

# Chama o uvicorn do venv direto, sem `uv run`: com `uv run` o container
# revalida e reconstroi o pacote a cada start, o que atrasa a subida e exige
# permissao de escrita em /app em tempo de execucao.
EXPOSE 8000
CMD ["uvicorn", "nfscan.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
