FROM python:3.9-slim

# Set pip to have no saved cache
ENV PIP_NO_CACHE_DIR=false \
    POETRY_VIRTUALENVS_CREATE=false

# Git is required to install a pinned version of d.py master
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install -U poetry

# Create the working directory
WORKDIR /bot

# Install project dependencies
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev

# Define Git SHA build argument
ARG git_sha="development"

# Set Git SHA environment variable for Sentry
ENV GIT_SHA=$git_sha

# Copy the source code in last to optimize rebuilding the image
COPY . .

CMD ["python", "-m", "bot"]
