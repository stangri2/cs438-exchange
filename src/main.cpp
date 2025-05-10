#include "EpollServer.hpp"
#include <cstdlib>
#include <iostream>

int main(int argc, char** argv)
{
    uint16_t port = (argc > 1) ? static_cast<uint16_t>(std::atoi(argv[1])) : 9000;
    std::cout << "Listening on tcp://0.0.0.0:" << port << '\n';
    try {
        srv::EpollServer srv(port);
        srv.run();
    } catch (...) {
        std::cerr << "fatal\n";
        return 1;
    }
}

