#ifndef ORDERBOOK_ORDERBOOK_HPP_
#define ORDERBOOK_ORDERBOOK_HPP_

#include <cstdint>
#include <functional>
#include <list>
#include <map>
#include <unordered_map>
#include <type_traits>

namespace OrderBook {

class OrderBook {
 private:
  enum class Side { BID, ASK };

  using OrderId = uint64_t;
  using Volume = uint64_t;
  using Price = uint64_t;

  struct Order {
    OrderId orderId;
    Price price;
    Volume volume;
    Side side;
  };

  std::map<Price, std::list<Order>> bids_;
  std::map<Price, std::list<Order>> asks_;
  std::unordered_map<OrderId, std::list<Order>::iterator> orderMap_;

 public:
  // TODO: Will need to figure out how the orderIds will be generated
  bool addOrder(OrderId orderId, Side side, Price price, Volume volume);

  bool modifyOrder(OrderId orderId, Volume newVolume);

  bool deleteOrder(OrderId orderId);
};
}  // namespace OrderBook

#endif
