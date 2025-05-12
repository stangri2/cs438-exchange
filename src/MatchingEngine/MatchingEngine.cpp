#include "MatchingEngine.hpp"
#include "DebugPrint.hpp"

#include <iostream>
#include <chrono>

namespace ex {

std::queue<Event> MatchingEngine::handle(const Command& cmd) {
    std::queue<Event> out;

    std::visit([](auto&& c){ std::cout << c << '\n'; }, cmd);

    std::visit([&](auto&& c) {
        using T = std::decay_t<decltype(c)>;
        if constexpr (std::is_same_v<T, CmdNew>) {
            Order o{ c.id, c.owner, c.price, c.qty, c.side,
                     std::chrono::steady_clock::now()
                         .time_since_epoch()
                         .count() };

            std::vector<Trade> trades;
            ob_.add(o, trades);

            ownerOf_[c.id] = c.owner;
            out.push(EvAckNew{ c.id });

            for (const auto& t : trades) {
                out.push(EvTrade{ t });
                std::cout << t << "\n";
            }

        } else if constexpr (std::is_same_v<T, CmdModify>) {
            if (ob_.modify(c.id, c.newQty))
                out.push(EvAckModify{ c.id });
            else {
                auto rejectEvent = EvReject{c.id}; 
                out.push(rejectEvent);
            }

        } else if constexpr (std::is_same_v<T, CmdCancel>) {
            if (ob_.cancel(c.id))
                out.push(EvAckCancel{ c.id });
            else {
                auto rejectEvent = EvReject{c.id}; 
                out.push(rejectEvent);
            }
        }
    }, cmd);

    return out;
}

} // namespace ex

