FROM rust:1.94.1 AS rust-builder

WORKDIR /src

# Build the updater binary.
COPY device-updater-rs ./device-updater-rs
RUN cargo build --manifest-path device-updater-rs/Cargo.toml --release

FROM python:3.11-slim

WORKDIR /app

RUN pip install poetry

COPY device-simulator/pyproject.toml device-simulator/poetry.lock* ./
RUN poetry config virtualenvs.create false && poetry install --no-root --no-interaction

COPY device-simulator/simulator.py device-simulator/updater.py device-simulator/start.sh ./
RUN chmod +x /app/start.sh

COPY --from=rust-builder /src/device-updater-rs/target/release/device-updater-rs /usr/local/bin/device-updater-rs

CMD ["/app/start.sh"]
