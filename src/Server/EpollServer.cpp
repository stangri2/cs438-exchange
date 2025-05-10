#include "EpollServer.hpp"
#include <arpa/inet.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <unistd.h>
#include <iostream>

#ifdef __APPLE__
  #include <sys/epoll.h>
#else
  #include <sys/epoll.h>
#endif


namespace srv {

/* ---------- helpers ------------------------------------------------ */
static int xcheck(int r, const char* ctx) {
    if (r == -1) { perror(ctx); std::exit(1); }
    return r;
}
void EpollServer::makeSocketNonBlocking(int fd)
{
    int flags = xcheck(fcntl(fd, F_GETFL, 0), "fcntl get");
    xcheck(fcntl(fd, F_SETFL, flags | O_NONBLOCK), "fcntl set");
}

/* ---------- ctor --------------------------------------------------- */
EpollServer::EpollServer(uint16_t port)
{
    listenFd_ = xcheck(::socket(AF_INET, SOCK_STREAM, 0), "socket");

    int yes = 1;
    setsockopt(listenFd_, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));

    sockaddr_in addr{};
    addr.sin_family      = AF_INET;
    addr.sin_port        = htons(port);
    addr.sin_addr.s_addr = INADDR_ANY;
    xcheck(::bind(listenFd_, (sockaddr*)&addr, sizeof(addr)), "bind");
    xcheck(::listen(listenFd_, 128), "listen");
    makeSocketNonBlocking(listenFd_);

    epfd_ = xcheck(epoll_create1(0), "epoll_create1");
    epoll_event ev{EPOLLIN, {.fd = listenFd_}};
    xcheck(epoll_ctl(epfd_, EPOLL_CTL_ADD, listenFd_, &ev), "epoll_ctl listen");
}

/* ---------- main loop ---------------------------------------------- */
void EpollServer::run()
{
    constexpr int MAXEV = 256;
    epoll_event events[MAXEV];

    for (;;) {
        int n = xcheck(epoll_wait(epfd_, events, MAXEV, -1), "epoll_wait");
        for (int i = 0; i < n; ++i) {
            int fd = events[i].data.fd;

            if (fd == listenFd_) {
                acceptClient();
            } else {
                if (events[i].events & EPOLLIN)  handleRead(fd);
                if (events[i].events & EPOLLOUT) handleWrite(fd);
                if (events[i].events & (EPOLLERR | EPOLLHUP)) closeClient(fd);
            }
        }
    }
}

/* ---------- accept -------------------------------------------------- */
void EpollServer::acceptClient()
{
    for (;;) {
        int fd = ::accept4(listenFd_, nullptr, nullptr, SOCK_NONBLOCK);
        if (fd == -1) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) break;
            perror("accept"); break;
        }
        epoll_event ev{EPOLLIN | EPOLLET, {.fd = fd}};
        xcheck(epoll_ctl(epfd_, EPOLL_CTL_ADD, fd, &ev), "epoll_ctl add");

        sessions_.emplace(fd, Session{});
        std::cout << "client " << fd << " connected\n";
    }
}

/* ---------- read / parse / engine ---------------------------------- */
void EpollServer::handleRead(int fd)
{
    auto& sess = sessions_[fd];
    char buf[4096];
    for (;;) {
        ssize_t n = ::recv(fd, buf, sizeof(buf), 0);
        if (n == -1 && (errno == EAGAIN || errno == EWOULDBLOCK)) break;
        if (n <= 0) { closeClient(fd); return; }

        sess.in.insert(sess.in.end(), buf, buf + n);

        std::queue<ex::Command> cmds;
        wire::decode(sess.in, cmds);

        while (!cmds.empty()) {
            auto cmd = std::move(cmds.front());
            cmds.pop();

            auto evq = engine_.handle(cmd);
            while (!evq.empty()) {
                std::string pkt;
                wire::encodeEvent(evq.front(), pkt);
                evq.pop();

                sess.out.push_back(std::move(pkt));
            }
        }
    }

    if (!sess.out.empty()) {
        epoll_event ev{EPOLLIN | EPOLLOUT | EPOLLET, {.fd = fd}};
        epoll_ctl(epfd_, EPOLL_CTL_MOD, fd, &ev);
    }
}

/* ---------- write --------------------------------------------------- */
void EpollServer::handleWrite(int fd)
{
    auto& sess = sessions_[fd];

    while (!sess.out.empty()) {
        const std::string& pkt = sess.out.front();
        ssize_t n = ::send(fd, pkt.data(), pkt.size(), 0);
        if (n == -1 && (errno == EAGAIN || errno == EWOULDBLOCK)) break;
        if (n == -1) { closeClient(fd); return; }
        sess.out.pop_front();
    }

    if (sess.out.empty()) {
        epoll_event ev{EPOLLIN | EPOLLET, {.fd = fd}};
        epoll_ctl(epfd_, EPOLL_CTL_MOD, fd, &ev);
    }
}

/* ---------- clean-up ----------------------------------------------- */
void EpollServer::closeClient(int fd)
{
    std::cout << "client " << fd << " disconnected\n";
    epoll_ctl(epfd_, EPOLL_CTL_DEL, fd, nullptr);
    ::close(fd);
    sessions_.erase(fd);
}

} // namespace srv

