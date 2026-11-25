# Imagem dos robôs da Elite para o Railway. O processo principal é a agenda (railway/agenda.py).
# Os dados ficam no volume montado em /dados (configurado no painel do Railway), nunca na imagem nem no GitHub.
FROM python:3.12-slim

RUN apt-get update -q && apt-get install -y -q --no-install-recommends curl ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x servidor/rodar.sh

ENV PYTHONUNBUFFERED=1 DADOS=/dados ELITE_ROBOS=/app
CMD ["python3", "railway/agenda.py"]
