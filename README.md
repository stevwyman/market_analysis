# market_analysis
django project to visualise stock market




ideas:

on the db model, we might want to use views on the history data to create a view by 


## Build and Run

points to check:

* where is the sqlite db pointing
* for bonds, check the selenium driver is pointing to the right one
* check logging

```sh
# build an image for the cloud container
docker buildx build --platform=linux/amd64 -t market_analysis .

# prepare for deployment
docker tag market_analysis stevwyman/market_analysis
docker push stevwyman/market_analysis

# create an internal network for the images
docker network create analysis_net

# Note: port 8001
docker run --net analysis_net --name analysis_py -p 8001:8001 market_analysis
docker run --net analysis_net --name analysis_mongo -p 27017:27017 mongo

# alternative add the image afterwards
docker network connect analysis_net mongo
docker network connect analysis_net market_analysis

docker network inspect analysis_net

docker network prune
```

## Virtual Env

```sh
python3 -m venv ~/virtualenv/market-analysis/
. ~/virtualenv/market-analysis/bin/activate
```


## MySQL

brew --prefix -> /opt/homebrew

export LDFLAGS="-L/opt/homebrew/lib -L/opt/homebrew/opt/openssl/lib -L/opt/homebrew/Cellar"

export CPPFLAGS="-I/opt/homebrew/include -I/opt/homebrew/opt/openssl/include"

## Selenium

using the follow setup
* Firefox 111.0
* GeckoDriver 0.33.0
* Selenium Server 4.9.0
* Release date 20230426

```sh
docker run -d -p 4444:4444 -p 7900:7900 --shm-size="2g" selenium/standalone-firefox:latest
docker network connect analysis_net standalone-firefox
```

as an alternative, we can install firefox inside the container
```sh
apt-get update && apt-get install -y wget bzip2 libxtst6 libgtk-3-0 libx11-xcb-dev libdbus-glib-1-2 libxt6 libpci-dev

mkdir /browsers
curl https://ftp.mozilla.org/pub/firefox/releases/61.0/linux-x86_64/en-US/firefox-61.0.tar.bz2 -o /browser/firefox-61.0.tar.bz2
tar xvf firefox-61.0.tar.bz2 -C /browsers

mkdir /drivers/
curl -L https://github.com/mozilla/geckodriver/releases/download/v0.32.0/geckodriver-v0.32.0-linux64.tar.gz -o /drivers/geckodrive.tar.gz
tar -xzvf /drivers/geckodrive.tar.gz -C /drivers/
```

and then using 

```py
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
 
options = Options()
options.binary_location = '/browsers/firefox'
driver = webdriver.Firefox(executable_path='/drivers/geckodrive', options=options)
driver.get("https://url.net/")
get_title = driver.title
print(get_title)
driver.close()
```