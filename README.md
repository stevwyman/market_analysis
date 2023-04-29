# market_analysis
django project to visualise stock market




ideas:

on the db model, we might want to use views on the history data to create a view by 


## Build and Run

```sh
# build an image for the cloud container
docker buildx build --platform=linux/amd64 -t market_analysis .

docker tag market_analysis YOUR_DOCKERHUB_NAME/market_analysis
docker push YOUR_DOCKERHUB_NAME/market_analysis

# create an internal network for the images
docker network create analysis_net

#Note: port 8001
docker run --net analysis_net --name analysis_py -p 8001:8001 market_analysis
docker run --net analysis_net --name loving_tesla -p 27017:27017 mongo

# alternative add the image afterwards
docker network connect mongo
docker network connect market_analysis

docker network inspect analysis_net

docker network prune
```
