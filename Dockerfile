FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SAFE_MODE=true \
    ABTP_PROFILE=paper \
    ABTP_TRADING_MODE=paper \
    ABTP_ENABLE_LIVE_TRADING=false \
    ABTP_ENABLE_PAPER_TRADING=true

WORKDIR /app

RUN useradd --create-home --shell /bin/bash abtp

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

EXPOSE 8765

USER abtp

CMD ["abtp-paper-dashboard", "--host", "0.0.0.0", "--port", "8765"]
