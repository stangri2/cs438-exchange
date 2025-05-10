Using Docker file: 
`docker-compose.yml'

We can create the sdn setup with routers as such:
```
docker compose up -d
```

We can turn off the setup with:
```
docker compuse down
```

We can completely wipe everything with:
```
docker compose down --volumes --remove-orphans
```

You can check which docker containers are running with:
```
docker ps -a
```