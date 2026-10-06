FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

WORKDIR /app

# ca-certificates needed for Telegram TLS; keep image slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY manager_82.py ./
COPY 95.py ./

# /opt/jafj is inside the image. A Railway Volume mounted at /app hides every
# file the image put there and keeps the previous ones forever, which is how an
# old manager_82.py / broken 95.py survived each redeploy. /opt/jafj cannot be
# shadowed, so the entrypoint runs the code from here and keeps only data on
# the Volume.
RUN mkdir -p /opt/jafj \
    && cp /app/manager_82.py /opt/jafj/manager_82.py \
    && cp /app/95.py /opt/jafj/95.py

COPY railway-start.sh render-start.sh /opt/jafj/
COPY tools/ /opt/jafj/tools/
RUN chmod 755 /opt/jafj/railway-start.sh /opt/jafj/render-start.sh

EXPOSE 8080

# Railway boots this by default; Render's blueprint (render.yaml) overrides the
# start command with `sh /opt/jafj/render-start.sh`.
CMD ["sh", "/opt/jafj/railway-start.sh"]
