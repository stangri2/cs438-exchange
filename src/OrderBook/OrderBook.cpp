#include "OrderBook.hpp"

#include <algorithm>
#include <chrono>

namespace ex {

/* ------------ helpers (file-local) ---------------- */
namespace {
using clock = std::chrono::steady_clock;
inline std::uint64_t now_ns() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
             clock::now().time_since_epoch())
      .count();
}
template <class T>
void eraseIfEmpty(T& tree, typename T::iterator it) {
  if (it->second.empty()) tree.erase(it);
}
}  // namespace

/* ================= template definition ================= */
template <Side S, class Opp, class Own>
void OrderBook::matchAgainst(Order& in, Opp& oppTree, Own& ownTree,
                             std::vector<Trade>& trades) {
  while (in.qty && !oppTree.empty()) {
    auto best = oppTree.begin();
    Price px = best->first;

    if constexpr (S == Side::BID) {
      if (px > in.price) break;
    } else {
      if (px < in.price) break;
    }

    auto& q = best->second;
    while (in.qty && !q.empty()) {
      Order& rest = q.front();
      Qty fill = std::min(in.qty, rest.qty);

      trades.push_back(
          {rest.id, in.id, rest.owner, in.owner, rest.price, fill});

      in.qty -= fill;
      rest.qty -= fill;

      if (rest.qty == 0) {
        id2it_.erase(rest.id);
        q.pop_front();
      }
    }
    eraseIfEmpty(oppTree, best);
  }

  if (in.qty) {
    auto& q = ownTree[in.price];
    q.push_back(in);
    id2it_[in.id] = std::prev(q.end());
  }
}

template <Side S>
bool OrderBook::cancelHelper(OrderId id) {
  /* ---------- locate the resting order ---------- */
  auto idIt = id2it_.find(id);
  if (idIt == id2it_.end()) return false;  // unknown ID

  auto nodeIt = idIt->second;  // iterator into the price-queue

  /* ---------- remove from the correct tree ---------- */
  if constexpr (S == Side::BID) {
    auto lvlIt = bids_.find(nodeIt->price);  // price-level in bid tree
    lvlIt->second.erase(nodeIt);             // O(1) erase from list
    eraseIfEmpty(bids_, lvlIt);              // drop level if list empty
  } else {                                   // S == Side::ASK
    auto lvlIt = asks_.find(nodeIt->price);
    lvlIt->second.erase(nodeIt);
    eraseIfEmpty(asks_, lvlIt);
  }

  /* ---------- forget the ID mapping ---------- */
  id2it_.erase(idIt);
  return true;
}

/* ------------ non-template members ---------------- */
bool OrderBook::add(const Order& ord, std::vector<Trade>& t) {
  Order in = ord;
  if (in.side == Side::BID)
    matchAgainst<Side::BID>(in, asks_, bids_, t);
  else
    matchAgainst<Side::ASK>(in, bids_, asks_, t);
  return true;
}

bool OrderBook::modify(OrderId id, Qty q) {
  auto it = id2it_.find(id);
  if (it == id2it_.end()) return false;
  it->second->qty = q;
  return true;
}
bool OrderBook::cancel(OrderId id) {
  auto idIt = id2it_.find(id);
  if (idIt == id2it_.end()) return false;  // unknown ID

  auto& nodeIt = idIt->second;  // iterator into the price-queue
  if (nodeIt->side == Side::BID) {
    return cancelHelper<Side::BID>(id);
  }
  return cancelHelper<Side::ASK>(id);
}

Price OrderBook::bestBid() const {
  return bids_.empty() ? 0 : bids_.begin()->first;
}
Price OrderBook::bestAsk() const {
  return asks_.empty() ? 0 : asks_.begin()->first;
}

/* ------------ explicit instantiations ---------------- */
template void OrderBook::matchAgainst<Side::BID>(Order&, AskMap&, BidMap&,
                                                 std::vector<Trade>&);
template void OrderBook::matchAgainst<Side::ASK>(Order&, BidMap&, AskMap&,
                                                 std::vector<Trade>&);

}  // namespace ex
