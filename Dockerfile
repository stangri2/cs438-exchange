# ── Stage 1 : build ────────────────────────────────────────────────
FROM ubuntu:22.04 AS build

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential cmake git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY . .

RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
 && cmake --build build -j$(nproc)

# ── Stage 2 : slim runtime image ───────────────────────────────────
FROM ubuntu:22.04

WORKDIR /app
# executable is in build/src/ because root CMakeLists.txt adds_subdirectory(src)
COPY --from=build /workspace/build/src/exchange .

EXPOSE 9000
CMD ["./exchange", "9000"]

