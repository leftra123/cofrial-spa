FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir "psycopg[binary]>=3.2"
COPY simulador.py .
RUN useradd --system --no-create-home simulador
USER simulador
CMD ["python", "simulador.py"]
