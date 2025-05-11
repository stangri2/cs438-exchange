#include <catch2/catch_test_macros.hpp>
#include "MatchingEngine.hpp"

using namespace ex;

TEST_CASE("Ack new order")
{
    MatchingEngine eng;
    auto evq = eng.handle(CmdNew{1, 9, Side::BID, 100, 5});
    REQUIRE(std::holds_alternative<EvAckNew>(evq.front()));
}

TEST_CASE("Unknown cancel is rejected")
{
    MatchingEngine eng;
    auto evq = eng.handle(CmdCancel{42});
    REQUIRE(std::holds_alternative<EvReject>(evq.front()));
}

