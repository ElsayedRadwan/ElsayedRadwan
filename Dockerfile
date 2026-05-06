FROM python:3.11-slim
ENV APP_HOME=/app
WORKDIR $APP_HOME
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -sSL https://sdk.cloud.google.com | bash \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/google-cloud-sdk/bin:${PATH}"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "app:app"]
