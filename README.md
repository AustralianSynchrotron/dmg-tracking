# Data Management Tracking Service
The data management tracking service provides a RESTful service for registration, retrieval and
tracking of changes for experimental datasets.


## Run the Service

#### Local Deployment for Development
If you would like to run the service locally for development purposes, create a python virtual
environment with pipenv and install the python packages with:

`pipenv --three install`

Activate the virtual environment:

`pipenv shell`

The data management tracking service communicates with the User Portal API and thus requires
valid credentials in order to authenticate with the User Portal. The service requires the following
environment variables to be set:

- `PORTAL_HOST`
- `PORTAL_CLIENT`
- `PORTAL_PASSWORD`

The best way to set those variables is to create a `.env` file with the following content:

```
PORTAL_HOST=https://portal.synchrotron.org.au/api/v1
PORTAL_CLIENT=[ask admin for client name]
PORTAL_PASSWORD=[ask admin for client password]
```

Start the service with:

`flask run`

or with auto-reloading enabled:

`flask run --reload`

You will also need a MongoDB server running on `localhost` listening on the default port `27017`.

#### Production Deployment
When running the service in production, it is highly recommended to use the provided Docker Compose
file and the Docker images from the Australian Synchrotron Docker registry. Run the service and the
database with:

`docker-compose up -d`

Please make sure that you have a `.env` file, as described above, in the same directory as the
Docker Compose file. Alternatively, set the environment variables with `export`.


## Build the Docker Container
Docker is the best way to run the data management tracking service. In order to build a Docker image,
execute the following command:

`docker build -t docker.synchrotron.org.au/dmg/dmg-tracking:latest .`

If the image is not available yet, push the image to our local Docker registry:

`docker push docker.synchrotron.org.au/dmg/dmg-tracking:latest`
