# syntax=docker/dockerfile:1

# machineplay runs this as `docker run --rm -i --network none …` and speaks UCI
# over stdin/stdout.

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# UCI is a line-based protocol over stdio: never buffer output.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so this layer stays cached until the lockfile changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY main.py ./

# Not `uv run`: it is slower to start and may want the network.
ENTRYPOINT [".venv/bin/python", "main.py"]
