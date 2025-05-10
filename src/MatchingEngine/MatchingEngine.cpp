#include "MatchingEngine.hpp"

namespace ex {

std::queue<Event> MatchingEngine::handle(const Command& cmd) {
    std::queue<Event> out;

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

            for (const auto& t : trades)
                out.push(EvTrade{ t });

        } else if constexpr (std::is_same_v<T, CmdModify>) {
            if (ob_.modify(c.id, c.newQty))
                out.push(EvAckModify{ c.id });
            else
                out.push(EvReject{ c.id, "unknown-order" });

        } else if constexpr (std::is_same_v<T, CmdCancel>) {
            if (ob_.cancel(c.id))
                out.push(EvAckCancel{ c.id });
            else
                out.push(EvReject{ c.id, "unknown-order" });
        }
    }, cmd);

    return out;
}

} // namespace ex

