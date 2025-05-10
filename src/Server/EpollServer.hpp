#pragma once
#include "MatchingEngine.hpp"
#include "MessageCodec.hpp"
#include <unordered_map>
#include <vector>
#include <deque>

namespace srv {

struct Session {
    std::vector<char>        in;     // raw bytes from recv()
    std::deque<std::string>  out;    // already-serialised wire packets
};

class EpollServer {
public:
    explicit EpollServer(uint16_t tcpPort);
    void run();                       /* blocks forever */

private:
    int               listenFd_{-1};
    int               epfd_{-1};
    ex::MatchingEngine engine_;
    std::unordered_map<int, Session> sessions_;     // fd → buffers

    void makeSocketNonBlocking(int fd);
    void acceptClient();
    void handleRead(int fd);
    void handleWrite(int fd);
    void closeClient(int fd);
};

} // namespace srv

