docker build -t sdn-fastapi-app .
docker run -d -p 8000:8000 --name sdn_app_container sdn-fastapi-app