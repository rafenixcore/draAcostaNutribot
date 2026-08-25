FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY manage.py ./
COPY core ./core
RUN pip install --no-cache-dir django
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
