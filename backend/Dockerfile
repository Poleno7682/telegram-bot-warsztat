FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install OS packages needed to build Python deps (deep-translator/aiosqlite wheels
# are usually prebuilt, but curl is kept for the healthcheck / debugging).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Compile gettext catalogs (locales/*/LC_MESSAGES/messages.po -> messages.mo).
# The app only reads the compiled .mo at runtime (stdlib gettext, no Babel
# needed there) - see locales/README.md for the edit workflow.
RUN pybabel compile -d locales -D messages

RUN useradd --create-home --uid 1000 --shell /bin/bash bot \
    && mkdir -p /app/db /app/logs \
    && chown -R bot:bot /app

USER bot

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["python", "-m", "app.main"]
