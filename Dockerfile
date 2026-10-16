FROM python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f AS build
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt
RUN python -c "import urllib.request,tarfile,io,pathlib; data=urllib.request.urlopen('https://codeload.github.com/twelvedata/mcp/tar.gz/d139a77ea0f7d40995e6979cd09c22dd142fbfe8').read(); tarfile.open(fileobj=io.BytesIO(data),mode='r:gz').extractall('/opt/twelve',filter='data')"

FROM python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    HOME=/home/appuser
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --from=build /opt/twelve /opt/twelve
ENV TWELVE_MCP_SCRIPT=/opt/twelve/mcp-d139a77ea0f7d40995e6979cd09c22dd142fbfe8/src/server.py
RUN useradd --create-home --uid 10001 appuser && mkdir -p /app/artifacts/quant && chown -R appuser:appuser /app
COPY --chown=appuser:appuser main.py ./
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser prompts/ ./prompts/
COPY --chown=appuser:appuser web/ ./web/
COPY --chown=appuser:appuser data/source_inventory.json ./data/source_inventory.json
USER appuser
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port \"${PORT}\""]
