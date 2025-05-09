#include "OrderBook.hpp"
#include <cassert>

namespace OrderBook {

bool OrderBook::addOrder(OrderId orderId, Side side, Price price, Volume volume) {
    // Check for duplicate orderId; if already exists, do not add.
    if (orderMap_.find(orderId) != orderMap_.end()) {
        return false;
    }

    // Create a new Order instance.
    Order newOrder { orderId, price, volume, side };

    // If the order is a bid, we match against asks,
    // otherwise (if an ask), we match against bids.
    if (side == Side::BID) {
        // *** Matching process for a BID order ***
        // A bid can match with resting asks whose prices are <= bid price.
        while (volume > 0 && !asks_.empty()) {
            // The best ask is the one with the lowest price.
            auto bestAskIt = asks_.begin();
            Price askPrice = bestAskIt->first;

            // If the best ask price is higher than the bid price, no match is possible.
            if (askPrice > price) {
                break;
            }

            // Process the list of orders at this price level.
            auto& askList = bestAskIt->second;
            while (volume > 0 && !askList.empty()) {
                // Matching with the resting order at the front (oldest order at this price level).
                Order& restingOrder = askList.front();
                if (restingOrder.volume <= volume) {
                    // Incoming order can fully fill this resting order.
                    volume -= restingOrder.volume;
                    // Remove the filled order from the order map.
                    orderMap_.erase(restingOrder.orderId);
                    // Remove from the ask price level.
                    askList.pop_front();
                } else {
                    // Partial fill: reduce the resting order's volume.
                    restingOrder.volume -= volume;
                    volume = 0;
                }
            }
            // If after matching the list for this price level becomes empty, remove it.
            if (askList.empty()) {
                asks_.erase(bestAskIt);
            }
        }
        // After matching, if there is remaining volume, add it as a resting bid.
        if (volume > 0) {
            newOrder.volume = volume;
            // Use negative price as key to maintain descending order in bids.
            Price bidKey = static_cast<Price>(-static_cast<int64_t>(price));
            std::list<Order>& bidList = bids_[bidKey];
            bidList.push_back(newOrder);
            // Save the iterator to this new order.
            auto orderIt = std::prev(bidList.end());
            orderMap_[orderId] = orderIt;
        }
    } else { // side == Side::ASK
        // *** Matching process for an ASK order ***
        // An ask can match with resting bids whose prices are >= ask price.
        while (volume > 0 && !bids_.empty()) {
            // The best bid is stored at the beginning of bids_,
            // but remember that bids are keyed as negative prices.
            auto bestBidIt = bids_.begin();
            // Recover the original bid price.
            Price bestBidPrice = static_cast<Price>(-static_cast<int64_t>(bestBidIt->first));

            // If the best bid price is lower than the ask price, no match can occur.
            if (bestBidPrice < price) {
                break;
            }

            // Process the list of orders at this bid price level.
            auto& bidList = bestBidIt->second;
            while (volume > 0 && !bidList.empty()) {
                Order& restingOrder = bidList.front();
                if (restingOrder.volume <= volume) {
                    // The ask fully fills this resting bid order.
                    volume -= restingOrder.volume;
                    orderMap_.erase(restingOrder.orderId);
                    bidList.pop_front();
                } else {
                    // Partial fill: adjust the resting order volume.
                    restingOrder.volume -= volume;
                    volume = 0;
                }
            }
            // Clean up empty price levels.
            if (bidList.empty()) {
                bids_.erase(bestBidIt);
            }
        }
        // If there is remaining volume, add it as a resting ask.
        if (volume > 0) {
            newOrder.volume = volume;
            std::list<Order>& askList = asks_[price];
            askList.push_back(newOrder);
            auto orderIt = std::prev(askList.end());
            orderMap_[orderId] = orderIt;
        }
    }

    // Return true to indicate the order was processed (filled or partially added).
    return true;
}

// Existing methods remain unchanged.
bool OrderBook::modifyOrder(OrderId orderId, Volume newVolume) {
    auto it = orderMap_.find(orderId);
    if (it == orderMap_.end()) {
        return false;
    }
    Order& order = *(it->second);
    if (order.volume < newVolume) {
        return false;
    }
    order.volume = newVolume;
    return true;
}

bool OrderBook::deleteOrder(OrderId orderId) {
    auto it = orderMap_.find(orderId);
    if (it == orderMap_.end()) {
        return false;
    }
    auto orderIt = it->second;
    const Order& order = *orderIt;
    Side side = order.side;
    bool isBid = (side == Side::BID);
    // For bids, the price key is stored as negative.
    Price orderPrice = isBid ? static_cast<Price>(-static_cast<int64_t>(order.price))
                             : order.price;
    std::map<Price, std::list<Order>>& book = isBid ? bids_ : asks_;
    auto priceQueueIt = book.find(orderPrice);
    assert(priceQueueIt != book.end());
    std::list<Order>& priceQueue = priceQueueIt->second;
    priceQueue.erase(orderIt);
    if (priceQueue.empty()) {
        book.erase(priceQueueIt);
    }
    orderMap_.erase(it);
    return true;
}

}  // namespace OrderBook

