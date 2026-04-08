FROM python:3.13-slim

# git CLI is required for BrainGitOps (commit/push to GitHub from the container)
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire repo INCLUDING .git so gitpython can operate at runtime.
# (Nixpacks would strip .git — that's why we use a Dockerfile.)
COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "src/bot.py"]
