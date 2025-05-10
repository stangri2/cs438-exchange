#pragma once
#include "OrderBook.hpp"
#include <queue>
#include <variant>

namespace ex {

struct CmdNew     { OrderId id; ClientId owner; Side side; Price price; Qty qty; };
struct CmdModify  { OrderId id; Qty newQty; };
struct CmdCancel  { OrderId id; };

using Command = std::variant<CmdNew, CmdModify, CmdCancel>;

/* --- outbound events to I/O layer ----------------------------------- */
struct EvAckNew     { OrderId id; };
struct EvAckModify  { OrderId id; };
struct EvAckCancel  { OrderId id; };
struct EvReject     { OrderId id; std::string reason; };
struct EvTrade      { Trade t; };   // full trade struct from OrderBook

using Event = std::variant<EvAckNew, EvAckModify, EvAckCancel, EvTrade, EvReject>;

class MatchingEngine {
public:
    /** Feed one command; returned queue contains *all* events to dispatch
        (client acks & trade prints for both counterparties).           */
    std::queue<Event> handle(const Command& cmd);

    /** Utility for market-data thread */
    Price bestBid() const { return ob_.bestBid(); }
    Price bestAsk() const { return ob_.bestAsk(); }

private:
    OrderBook ob_;
    std::unordered_map<OrderId, ClientId> ownerOf_;
};

} // namespace ex

