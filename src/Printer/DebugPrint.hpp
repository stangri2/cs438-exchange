#pragma once
#include <iostream>
#include "OrderBook.hpp"      // Trade
#include "MatchingEngine.hpp" // Cmd* + EvTrade

namespace ex {

// ---------- pretty printer helpers ----------
inline const char* toString(Side s) { return s == Side::BID ? "BID" : "ASK"; }

// ---------- inbound commands ----------
inline std::ostream& operator<<(std::ostream& os, const CmdNew& c) {
    return os << "NEW  id=" << c.id << " owner=" << c.owner
              << " side="  << toString(c.side)
              << " px="    << c.price
              << " qty="   << c.qty;
}
inline std::ostream& operator<<(std::ostream& os, const CmdModify& c) {
    return os << "MOD  id=" << c.id << " newQty=" << c.newQty;
}
inline std::ostream& operator<<(std::ostream& os, const CmdCancel& c) {
    return os << "CXL  id=" << c.id;
}

// ---------- execution prints ----------
inline std::ostream& operator<<(std::ostream& os, const Trade& t) {
    return os << "TRADE maker=" << t.maker
              << " taker="     << t.taker
              << " px="        << t.price
              << " qty="       << t.qty;
}
inline std::ostream& operator<<(std::ostream& os, const EvTrade& e) {
    return os << e.t;
}

} // namespace ex

