# ── Stage 1 : build & test ───────────────────────────────────────────
FROM ubuntu:22.04 AS build

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        ca-certificates \          
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY . .

# configure, build *and* run tests
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
 && cmake --build build -j$(nproc) \
 # build the merged-tests target
 && cmake --build build --target unit_tests \
 # run the tests (fails the layer if any test fails)
 && cd build && ctest --output-on-failure

# ── Stage 2 : slim runtime image ───────────────────────────────────
FROM ubuntu:22.04

WORKDIR /app
# executable ends up in build/src/ (because src/CMakeLists.txt adds_subdirectory)
COPY --from=build /workspace/build/src/exchange .

EXPOSE 9000
CMD ["./exchange", "9000"]

