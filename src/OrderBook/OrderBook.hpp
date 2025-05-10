#pragma once
#include <cstdint>
#include <list>
#include <map>
#include <unordered_map>
#include <vector>

namespace ex {

using OrderId = std::uint64_t;
using ClientId = std::uint32_t;
using Price    = std::int64_t;
using Qty      = std::uint32_t;

enum class Side : std::uint8_t { BID, ASK };

struct Order { OrderId id; ClientId owner; Price price; Qty qty; Side side; long timestamp;};
struct Trade { OrderId maker, taker; ClientId makerOwner, takerOwner;
               Price price; Qty qty; };

class OrderBook {
public:
    bool add   (const Order&, std::vector<Trade>&);
    bool modify(OrderId, Qty);
    bool cancel(OrderId);
    Price bestBid () const;
    Price bestAsk () const;

private:
    using Queue  = std::list<Order>;
    using BidMap = std::map<Price, Queue, std::greater<>>;
    using AskMap = std::map<Price, Queue, std::less<>>;

    BidMap bids_;
    AskMap asks_;
    std::unordered_map<OrderId, Queue::iterator> id2it_;

    template<Side S, class Opp, class Own>
    void matchAgainst(Order& in, Opp& oppTree, Own& ownTree,
                      std::vector<Trade>& out);
    template<Side s>
    bool cancelHelper(OrderId);
};

} // namespace ex

