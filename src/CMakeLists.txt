
# -------------------------------------------------------------------
# OrderBook  (leaf library)
# -------------------------------------------------------------------
add_library(orderbook STATIC
    OrderBook/OrderBook.cpp
)
target_include_directories(orderbook
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/OrderBook
)

# -------------------------------------------------------------------
# MatchingEngine  (depends on OrderBook)
# -------------------------------------------------------------------
add_library(matching_engine STATIC
    MatchingEngine/MatchingEngine.cpp
)
target_include_directories(matching_engine
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/MatchingEngine
)
target_link_libraries(matching_engine
    PUBLIC orderbook          # propagate include dirs to dependents
)

# -------------------------------------------------------------------
# Wire / MessageCodec  (depends on MatchingEngine)
# -------------------------------------------------------------------
add_library(message_codec STATIC
    Wire/MessageCodec.cpp
)
target_include_directories(message_codec
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/Wire
)
target_link_libraries(message_codec
    PUBLIC matching_engine    # so its users see MatchingEngine headers
)

# -------------------------------------------------------------------
# Epoll server wrapper  (depends on MessageCodec)
# -------------------------------------------------------------------
add_library(epoll_server STATIC
    Server/EpollServer.cpp
)
target_include_directories(epoll_server
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/Server
)
target_link_libraries(epoll_server
    PUBLIC message_codec      # pulls in codec → engine → book
)
# ---- macOS epoll-shim ------------------------------------------------
if(APPLE)
    # Hard-code Homebrew prefix; adjust if yours differs
    set(EPOLL_SHIM_ROOT "/opt/homebrew/opt/epoll-shim")

    target_include_directories(epoll_server
        PUBLIC "${EPOLL_SHIM_ROOT}/include/libepoll-shim")

    target_link_libraries(epoll_server
        PUBLIC "${EPOLL_SHIM_ROOT}/lib/libepoll-shim.dylib")
endif()

# -------------------------------------------------------------------
# Executable
# -------------------------------------------------------------------
add_executable(exchange
    main.cpp
)
find_package(Threads REQUIRED)             # portable pthreads
target_link_libraries(exchange
    PRIVATE epoll_server
    PRIVATE Threads::Threads
)

# Convenience: `make run` ⇒ ./exchange 4000
add_custom_target(run
    COMMAND exchange 4000
    DEPENDS exchange
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
)


