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
docker compose down -volumes --remove-orphans -v
docker compose build sdn_controller
docker compose build router1 router2 router3 router4 router5 router6 router7 router8 router9 router10
docker compose build exchange_server
docker compose build exchange_client
docker compose up -d

docker logs sdn_controller
```

You can view the created network topollogy with:
```
http://localhost:8000/sdn_controller/graph
```

You can generate a video of the network paths throughout time with:
```
cd /cs438-exchange/network
ffmpeg -framerate 5 -pattern_type glob -i 'shared/snapshots/network_graph_*.png' -c:v libx264 -pix_fmt yuv420p network_evolution.mp4
```