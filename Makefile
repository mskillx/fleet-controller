build:
	docker compose build

run:
	docker compose up --build --scale device-simulator=15