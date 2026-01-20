# Base Image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Set working directory
WORKDIR /app

# Install System Dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry \
    && poetry config virtualenvs.create false

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Copy local wheel if it exists (using wildcards effectively makes this optional if files match)
COPY *.whl ./

# Install Dependencies
# Note: We use --no-root to avoid installing the package itself at this stage
# ensuring we can cache dependencies layer.
RUN poetry install --no-dev --no-interaction --no-ansi --no-root

# Download Spacy Models
RUN python -m spacy download en_core_web_md
RUN python -m spacy download el_core_news_lg

# Copy Source Code and Data
COPY src/ ./src/
COPY data/ ./data/

# Expose the port
EXPOSE 8000

# Entrypoint
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
