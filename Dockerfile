FROM python:3.9-slim
RUN apt-get update && apt-get install -y ffmpeg
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]