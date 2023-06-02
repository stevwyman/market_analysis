# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.10-slim

EXPOSE 8001

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Set the polygon.io API key
ENV POLYGON_API_KEY=###

# Set the Tiingo API key
ENV TIINGO_API_KEY=###

# Set the mongodb host
ENV MONGODB_HOST=localhost

# Create a volume
VOLUME /data/market_analysis

COPY . /usr/src/app
WORKDIR /usr/src/app

# Install pip requirements
RUN pip install -r requirements.txt

CMD ["python3", "manage.py", "runserver", "0.0.0.0:8001"]
