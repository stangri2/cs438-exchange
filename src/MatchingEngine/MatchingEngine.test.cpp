#include <catch2/catch_test_macros.hpp>
#include "MatchingEngine.hpp"

using namespace ex;

/* helpers */
static CmdNew mkNew(OrderId id, ClientId owner, Side s, Price px, Qty q)
{
    return {id, owner, s, px, q};
}

/* ------------------------------------------------------------------ */
TEST_CASE("New order is ACKed")
{
    MatchingEngine eng;
    auto q = eng.handle(mkNew(1, 10, Side::BID, 100, 3));

    REQUIRE(q.size() == 1);
    REQUIRE(std::holds_alternative<EvAckNew>(q.front()));
}

/* ------------------------------------------------------------------ */
TEST_CASE("Crossing order generates trade event")
{
    MatchingEngine eng;

    /* 1. Post resting bid */
    eng.handle(mkNew(1, 11, Side::BID, 100, 5));   // ACK (ignored here)

    /* 2. Add ask that crosses */
    auto q = eng.handle(mkNew(2, 22, Side::ASK, 95, 5));

    REQUIRE(q.size() == 2);                        // Ack + Trade
    REQUIRE(std::holds_alternative<EvAckNew>(q.front()));
    q.pop();
    auto tr = std::get<EvTrade>(q.front()).t;
    REQUIRE(tr.maker == 1);                        // maker = resting order
    REQUIRE(tr.taker == 2);
    REQUIRE(tr.price == 100);
    REQUIRE(tr.qty   == 5);
}

/* ------------------------------------------------------------------ */
TEST_CASE("Partial fill leaves residual on book")
{
    MatchingEngine eng;
    eng.handle(mkNew(1, 30, Side::ASK, 110, 10));         // resting ask

    /* aggressive bid only fills half */
    auto q = eng.handle(mkNew(2, 31, Side::BID, 120, 4));

    /* Ack + Trade */
    REQUIRE(q.size() == 2);
    q.pop();
    auto tr = std::get<EvTrade>(q.front()).t;
    REQUIRE(tr.qty == 4);

    /* best ask should still be 110 (6 left) */
    REQUIRE(eng.bestAsk() == 110);
}

/* ------------------------------------------------------------------ */
TEST_CASE("Modify succeeds and unknown modify is rejected")
{
    MatchingEngine eng;
    eng.handle(mkNew(1, 40, Side::BID, 90, 8));            // ACK

    /* valid modify */
    auto ok = eng.handle(CmdModify{1, 3});
    REQUIRE(std::holds_alternative<EvAckModify>(ok.front()));

    /* unknown modify */
    auto rej = eng.handle(CmdModify{99, 5});
    REQUIRE(std::holds_alternative<EvReject>(rej.front()));
}

/* ------------------------------------------------------------------ */
TEST_CASE("Cancel succeeds and unknown cancel is rejected")
{
    MatchingEngine eng;
    eng.handle(mkNew(1, 50, Side::ASK, 130, 2));           // ACK

    /* valid cancel */
    auto ok = eng.handle(CmdCancel{1});
    REQUIRE(std::holds_alternative<EvAckCancel>(ok.front()));

    /* already gone */
    auto rej = eng.handle(CmdCancel{1});
    REQUIRE(std::holds_alternative<EvReject>(rej.front()));
}

