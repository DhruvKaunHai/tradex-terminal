# Minimal zero-dependency container for NSE Quant Studio
FROM python:3.11-slim

WORKDIR /app

# Copy all application files
COPY . /app

# Expose HTTP port
EXPOSE 8080

# Environment variables
ENV PYTHONUNBUFFERED=1

# Run the terminal server
CMD ["python", "server.py"]
