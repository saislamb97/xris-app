# Run this from your terminal:
chmod +x entrypoint.sh

# 1. Build all images
docker compose build

# 2. Start containers in detached mode
docker compose up -d

docker compose ps   

# 3. Tail logs to watch for errors
docker compose logs -f

docker compose build --no-cache
docker compose up -d

docker compose logs -f web

docker compose down -v
docker compose up --build

docker compose up -d --build
