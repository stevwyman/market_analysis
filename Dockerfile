# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.11-slim

#RUN apt-get update && apt-get -y install cron && touch /var/log/cron.log

EXPOSE 8001

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Set the polygon.io API key
ENV POLYGON_API_KEY=###

# Set the Tiingo API key
ENV TIINGO_API_KEY=###

# Set the Tiingo API key
ENV COMWYCA_API_KEY=###

# Set the mongodb host
ENV MONGODB_HOST=mongo

# Create a volume
VOLUME /data/market_analysis

COPY . /usr/src/app
WORKDIR /usr/src/app

# Install pip requirements
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

#CMD ["python3", "manage.py", "runserver", "0.0.0.0:8001"]
#RUN ["chmod", "+x", "/usr/src/app/docker-entrypoint.sh"]
#ENTRYPOINT ["/usr/src/app/docker-entrypoint.sh"]  # must be JSON-array syntax
CMD ["./manage.py", "runserver", "0.0.0.0:8001"]  # as before
