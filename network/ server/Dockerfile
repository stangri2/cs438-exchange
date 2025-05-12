# ── Stage 1 : build & test ───────────────────────────────────────────
FROM ubuntu:22.04 AS build

ENV DEBIAN_FRONTEND=noninteractive

# tool-chain + python + CA bundle
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    ca-certificates \
    python3 \
    python3-pip && \
    update-ca-certificates && \
    pip3 install --no-cache-dir pytest && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
# Copy source code from mounted volume
COPY ./src /workspace/src
COPY ./CMakeLists.txt /workspace/CMakeLists.txt

# configure, build, **unit-test**, **E2E-test**
RUN cmake -S src -B build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build -j$(nproc) \
    && cmake --build build --target unit_tests \
    && cd build && ctest --output-on-failure \
    && cd /workspace && pytest -q tests/e2e

# ── Stage 2 : slim runtime image ────────────────────────────────────
FROM ubuntu:22.04

WORKDIR /app
# executable produced in build/src/
COPY --from=build /workspace/build/src/exchange .

# EXPOSE 6000
# CMD ["./exchange", "6000"]

