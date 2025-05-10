cmake_minimum_required(VERSION 3.15)
project(Exchange LANGUAGES CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS ON)

# OrderBook library
add_library(orderbook STATIC
    src/OrderBook/Orderbook.cpp
)

target_include_directories(orderbook PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src/OrderBook
)

# Matching Engine executable
add_library(matching_engine
    src/MatchingEngine/MatchingEngine.cpp
)

target_include_directories(orderbook PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src/MatchingEngine
)

# Link OrderBook to MatchingEngine
target_link_libraries(matching_engine PRIVATE orderbook)

add_library(message_codec STATIC src/Wire/MessageCodec.cpp)

target_include_directories(orderbook PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src/Wire
)

target_link_libraries(message_codec PRIVATE matching_engine)
