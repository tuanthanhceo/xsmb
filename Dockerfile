FROM python:3.11-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv pip install --system -e ".[dev]"

COPY . .

ENTRYPOINT ["python", "-m", "src.main"]
