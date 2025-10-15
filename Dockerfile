# Use a lightweight Python base image
FROM python:3.11-slim

# Set environment variables for the application
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV FLASK_APP=app.py

# Create and set the working directory
WORKDIR /usr/src/app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port (Gunicorn will run on this port)
EXPOSE 8080

# Command to run the application using Gunicorn
# -w N: Number of worker processes (usually 2x cores + 1)
# -b 0.0.0.0:8080: Bind to all interfaces on port 8080
# app:app: The Flask app object in the app.py file
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8080", "app:app"]