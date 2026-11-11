FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./requirements.txt
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY trading_agent ./trading_agent
COPY backend/app ./backend/app
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
