FROM python:3.12-slim

# tesseract-ocr-por e o que da precisao em texto acentuado; poppler-utils traz
# pdftotext e pdftoppm, usados para preservar colunas e renderizar PDF-imagem.
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-por poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --all-extras --no-dev

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "nfscan.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
