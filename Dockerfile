FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TASKFLOW_ENV=production
ENV TASKFLOW_AUTO_INIT_DB=false
ENV PORT=7860

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/start_api.sh

EXPOSE 7860

CMD ["/app/start_api.sh"]