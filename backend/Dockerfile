FROM python:3.11-slim

RUN groupadd -r trustdesk && useradd -r -g trustdesk trustdesk

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER trustdesk

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
