FROM python:3.12-slim

WORKDIR /app

COPY . .

ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "main"]