#include <catch2/catch_test_macros.hpp>
#include "OrderBook.hpp"

using namespace ex;

static Order mk(OrderId id, Side s, Price px, Qty q)
{
    return {id, /*owner=*/7, px, q, s, 0};
}

TEST_CASE("best prices update")
{
    OrderBook ob;
    std::vector<Trade> t;

    ob.add(mk(1, Side::BID, 100, 10), t);
    REQUIRE(ob.bestBid() == 100);
    REQUIRE(ob.bestAsk() == 0);

    ob.add(mk(2, Side::ASK, 105, 8), t);
    REQUIRE(ob.bestAsk() == 105);
}

TEST_CASE("crossing order matches")
{
    OrderBook ob; std::vector<Trade> t;
    ob.add(mk(1, Side::BID, 100, 10), t); t.clear();

    ob.add(mk(2, Side::ASK,  99, 6), t);
    REQUIRE(t.size() == 1);
    REQUIRE(t[0].qty   == 6);
    REQUIRE(t[0].price == 100);
}

