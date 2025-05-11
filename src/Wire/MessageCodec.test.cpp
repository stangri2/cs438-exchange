#include <catch2/catch_test_macros.hpp>
#include "Wire/MessageCodec.hpp"
#include "MatchingEngine.hpp"
#include <cstring>

namespace w = wire;
using namespace ex;

/* ------------------------------------------------------------------ */
/* helpers to craft raw packets                                        */
/* ------------------------------------------------------------------ */
static std::vector<char> makeNewRaw(CmdNew c)
{
    std::vector<char> raw(26);
    raw[0] = 0;                                   // MsgType::NEW
    std::memcpy(&raw[1],  &c.owner, 4);
    std::memcpy(&raw[5],  &c.id,    8);
    raw[13] = static_cast<std::uint8_t>(c.side);
    std::memcpy(&raw[14], &c.price, 8);
    std::memcpy(&raw[22], &c.qty,   4);
    return raw;
}
static std::vector<char> makeModRaw(CmdModify c)
{
    std::vector<char> raw(17);
    raw[0] = 1;                                   // MsgType::MODIFY
    std::uint32_t dummyOwner = 0;
    std::memcpy(&raw[1],  &dummyOwner, 4);        // still parsed
    std::memcpy(&raw[5],  &c.id, 8);
    std::memcpy(&raw[13], &c.newQty, 4);
    return raw;
}
static std::vector<char> makeCxlRaw(CmdCancel c)
{
    std::vector<char> raw(13);
    raw[0] = 2;                                   // MsgType::CANCEL
    std::uint32_t dummyOwner = 0;
    std::memcpy(&raw[1],  &dummyOwner, 4);
    std::memcpy(&raw[5],  &c.id, 8);
    return raw;
}

/* ------------------------------------------------------------------ */
/* 1.  Round-trip decode for all three inbound message types            */
/* ------------------------------------------------------------------ */
TEST_CASE("decode NEW/MODIFY/CANCEL")
{
    std::queue<Command> q;

    CmdNew nw{10, 7, Side::BID, 123, 5};
    auto rawN = makeNewRaw(nw);
    REQUIRE(w::decode(rawN, q) == 26);
    REQUIRE(std::get<CmdNew>(q.front()).id == 10);
    q.pop();

    CmdModify md{11, 99};
    auto rawM = makeModRaw(md);
    REQUIRE(w::decode(rawM, q) == 17);
    REQUIRE(std::get<CmdModify>(q.front()).newQty == 99);
    q.pop();

    CmdCancel cx{12};
    auto rawC = makeCxlRaw(cx);
    REQUIRE(w::decode(rawC, q) == 13);
    REQUIRE(std::get<CmdCancel>(q.front()).id == 12);
}

/* ------------------------------------------------------------------ */
/* 2.  Partial packet should not decode until complete                 */
/* ------------------------------------------------------------------ */
TEST_CASE("decoder waits for full packet")
{
    CmdNew nw{20, 7, Side::ASK, 555, 3};
    auto raw = makeNewRaw(nw);

    std::queue<Command> q;
    std::vector<char> buf(raw.begin(), raw.begin() + 10);   // first 10 bytes
    REQUIRE(w::decode(buf, q) == 0);
    REQUIRE(q.empty());

    buf.insert(buf.end(), raw.begin() + 10, raw.end());     // rest of bytes
    REQUIRE(w::decode(buf, q) == 26);                       // now consumed
    REQUIRE(std::get<CmdNew>(q.front()).id == 20);
}

/* ------------------------------------------------------------------ */
/* 3.  Encode each outbound event type                                 */
/* ------------------------------------------------------------------ */
TEST_CASE("encode outbound events")
{
    std::string pkt;

    w::encodeEvent(EvAckNew{1}, pkt);
    REQUIRE(pkt.size() == 1 + sizeof(OrderId));
    REQUIRE(pkt[0] == 'A');
    pkt.clear();

    w::encodeEvent(EvAckModify{2}, pkt);
    REQUIRE(pkt[0] == 'M');
    pkt.clear();

    w::encodeEvent(EvAckCancel{3}, pkt);
    REQUIRE(pkt[0] == 'C');
    pkt.clear();

    w::encodeEvent(EvReject{4}, pkt);
    REQUIRE(pkt[0] == 'R');
    REQUIRE(pkt.size() == 1 + sizeof(OrderId));
    pkt.clear();

    Trade tr{5, 6, 7, 8, 999, 4};
    w::encodeEvent(EvTrade{tr}, pkt);
    REQUIRE(pkt[0] == 'T');
    REQUIRE(pkt.size() == 1 + 2*sizeof(OrderId) + sizeof(Price) + sizeof(Qty));
}

