FROM python:3.11-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY db ./db
COPY static ./static
RUN useradd --system --no-create-home app
USER app
# --no-access-log: não registra IP + rota de cada requisição (anonimato dos usuários).
# PORT é definido pelo provedor de hospedagem (Render, Koyeb...); 8000 localmente.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log --no-server-header --proxy-headers --forwarded-allow-ips="*" --ws-per-message-deflate false
