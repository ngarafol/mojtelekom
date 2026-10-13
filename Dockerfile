FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY mojtelekom ./mojtelekom
RUN pip install --no-cache-dir .

EXPOSE 8088
CMD ["mojtelekom", "serve", "--host", "0.0.0.0"]
