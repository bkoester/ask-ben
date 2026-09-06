FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY askben ./askben
COPY evals ./evals
COPY corpus ./corpus
COPY scripts ./scripts
RUN pip install --no-cache-dir . && rm -rf /root/.cache
EXPOSE 8080
CMD ["uvicorn", "askben.api:app", "--host", "0.0.0.0", "--port", "8080"]
