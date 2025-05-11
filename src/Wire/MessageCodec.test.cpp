#include <catch2/catch_test_macros.hpp>
#include "Wire/MessageCodec.hpp"
#include "MatchingEngine.hpp"
#include <cstring>

namespace w = wire;
using namespace ex;

static std::vector<char> makeNewRaw(CmdNew c)
{
    std::vector<char> raw(26);
    raw[0] = 0;                                 // MsgType::NEW
    std::memcpy(&raw[1],  &c.owner, 4);
    std::memcpy(&raw[5],  &c.id,    8);
    raw[13] = static_cast<std::uint8_t>(c.side);
    std::memcpy(&raw[14], &c.price, 8);
    std::memcpy(&raw[22], &c.qty,   4);
    return raw;
}

TEST_CASE("decode NEW then encode ACK")
{
    CmdNew in{7, 11, Side::ASK, 123, 3};

    std::queue<Command> q;
    auto raw = makeNewRaw(in);
    w::decode(raw, q);

    REQUIRE(!q.empty());
    auto out = std::get<CmdNew>(q.front());
    REQUIRE(out.id == in.id);
    REQUIRE(out.price == in.price);

    std::string wireBuf;
    w::encodeEvent(EvAckNew{in.id}, wireBuf);
    REQUIRE(wireBuf.size() == 1 + sizeof(OrderId));   // 'A' + id
    REQUIRE(wireBuf[0] == 'A');
}

