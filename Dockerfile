# Swing B3 num container só: o FastAPI serve a API e o build do React no mesmo endereço.
# Funciona no Hugging Face Spaces (porta 7860, usuário 1000) e em serviços que definem PORT, como o Render.
# O banco fica em /app/data, dentro do container: em hospedagem gratuita ele começa vazio a cada
# reinício, e o app baixa de novo do Yahoo, desde 2010, os ativos consultados.

# 1. Build do frontend
FROM node:22-slim AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2. Backend + build
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    SWING_B3_FRONTEND=/app/frontend_dist
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=frontend /src/dist ./frontend_dist
RUN mkdir -p /app/data && chown -R app:app /app/data
USER app
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
