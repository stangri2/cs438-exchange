Using Docker file: 
`docker-compose.yml'

We can create the sdn setup with routers as such:
```
docker compose up -d
```

We can turn off the setup with:
```
docker compose down
```

We can completely wipe everything with:
```
docker compose down --volumes --remove-orphans
```

You can check which docker containers are running with:
```
docker ps -a
```

```
docker compose down
docker compose build sdn_controller
docker compose build router1 router2
docker compose up -d

docker logs sdn_controller
```

You can view the created network topollogy with:
```
http://localhost:8000/sdn_controller/graph
```