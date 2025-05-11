#include <catch2/catch_test_macros.hpp>
#include "OrderBook.hpp"

using namespace ex;

static Order mk(OrderId id, Side s, Price px, Qty q, ClientId owner = 7)
{
    return {id, owner, px, q, s, 0};
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

TEST_CASE("crossing order matches fully")
{
    OrderBook ob;
    std::vector<Trade> t;

    ob.add(mk(1, Side::BID, 100, 10), t); t.clear();
    ob.add(mk(2, Side::ASK,  99, 10), t);

    REQUIRE(t.size() == 1);
    REQUIRE(t[0].qty   == 10);
    REQUIRE(t[0].price == 100);
    REQUIRE(ob.bestBid() == 0);
    REQUIRE(ob.bestAsk() == 0);
}

TEST_CASE("crossing order partially fills and leaves remainder")
{
    OrderBook ob;
    std::vector<Trade> t;

    ob.add(mk(1, Side::BID, 100, 10), t); t.clear();
    ob.add(mk(2, Side::ASK,  99, 6), t);

    REQUIRE(t.size() == 1);
    REQUIRE(t[0].qty == 6);
    REQUIRE(ob.bestBid() == 100);
    REQUIRE(ob.bestAsk() == 0);
}

TEST_CASE("FIFO matching at same price level")
{
    OrderBook ob;
    std::vector<Trade> t;

    ob.add(mk(1, Side::BID, 100, 5), t);
    ob.add(mk(2, Side::BID, 100, 7), t);
    ob.add(mk(3, Side::ASK,  99, 10), t); // Should match with ID 1 then ID 2

    REQUIRE(t.size() == 2);
    REQUIRE(t[0].maker == 1);
    REQUIRE(t[0].qty == 5);
    REQUIRE(t[1].maker == 2);
    REQUIRE(t[1].qty == 5);
}

TEST_CASE("cancel removes order correctly")
{
    OrderBook ob;
    std::vector<Trade> t;

    ob.add(mk(1, Side::BID, 100, 10), t);
    REQUIRE(ob.bestBid() == 100);
    REQUIRE(ob.cancel(1));
    REQUIRE(ob.bestBid() == 0);
    REQUIRE_FALSE(ob.cancel(1)); // already cancelled
}

TEST_CASE("modify updates quantity but not price")
{
    OrderBook ob;
    std::vector<Trade> t;

    ob.add(mk(1, Side::ASK, 105, 10), t);
    REQUIRE(ob.bestAsk() == 105);
    REQUIRE(ob.modify(1, 4));
    ob.add(mk(2, Side::BID, 106, 10), t);

    REQUIRE(t.size() == 1);
    REQUIRE(t[0].qty == 4);
    REQUIRE(t[0].price == 105);
}

TEST_CASE("unknown cancel and modify fail gracefully")
{
    OrderBook ob;
    REQUIRE_FALSE(ob.cancel(999));
    REQUIRE_FALSE(ob.modify(888, 10));
}

TEST_CASE("multiple orders at different price levels maintain sorting")
{
    OrderBook ob;
    std::vector<Trade> t;

    ob.add(mk(1, Side::BID, 95, 1), t);
    ob.add(mk(2, Side::BID, 100, 1), t);
    ob.add(mk(3, Side::ASK, 110, 1), t);
    ob.add(mk(4, Side::ASK, 105, 1), t);

    REQUIRE(ob.bestBid() == 100);
    REQUIRE(ob.bestAsk() == 105);
}

