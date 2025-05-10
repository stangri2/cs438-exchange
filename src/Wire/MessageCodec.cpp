#include "MessageCodec.hpp"
#include <cstring>

namespace wire {

/* ---------- endian helpers (host == little-endian) ------------------ */
template<class T> inline T rd(const char* p)
{
    T v; std::memcpy(&v, p, sizeof(T)); return v;
}
inline void wr(std::string& out, const auto& v)
{
    out.append(reinterpret_cast<const char*>(&v), sizeof(v));
}

/* ---------- protocol sizes ----------------------------------------- */
enum class MsgType : std::uint8_t { NEW = 0, MODIFY = 1, CANCEL = 2 };

static constexpr std::size_t pktSize(MsgType t)
{
    switch (t) {
        case MsgType::NEW   : return 26;
        case MsgType::MODIFY: return 17;
        case MsgType::CANCEL: return 13;
    }
    return 0;
}

/* =================================================================== */
/*                               DECODER                               */
/* =================================================================== */
std::size_t decode(std::vector<char>& buf,
                   std::queue<ex::Command>& out)
{
    using namespace ex;
    std::size_t consumed = 0;

    while (!buf.empty()) {

        MsgType t = static_cast<MsgType>(buf[0]);
        std::size_t need = pktSize(t);
        if (need == 0 || buf.size() < need) break;          // unknown/partial

        const char* p = buf.data() + 1;

        ClientId cid = rd<ClientId>(p); p += 4;             // still parsed
        OrderId  oid = rd<OrderId >(p); p += 8;

        switch (t) {

        case MsgType::NEW: {
            auto  side = static_cast<Side>(*p++);           // 1 byte
            Price price = rd<Price>(p); p += 8;
            Qty   qty   = rd<Qty  >(p);
            out.push(ex::CmdNew{oid, cid, side, price, qty});
            break;
        }

        case MsgType::MODIFY: {
            Qty newQty = rd<Qty>(p);
            out.push(ex::CmdModify{oid, newQty});
            break;
        }

        case MsgType::CANCEL:
            out.push(ex::CmdCancel{oid});
            break;
        }

        buf.erase(buf.begin(), buf.begin() + need);
        consumed += need;
    }
    return consumed;
}

/* =================================================================== */
/*                               ENCODER                               */
/* =================================================================== */
void encodeEvent(const ex::Event& ev, std::string& dst)
{
    std::visit([&](auto&& e) {

        using T = std::decay_t<decltype(e)>;

        if constexpr (std::is_same_v<T, ex::EvAckNew>) {
            dst.push_back('A'); wr(dst, e.id);

        } else if constexpr (std::is_same_v<T, ex::EvAckModify>) {
            dst.push_back('M'); wr(dst, e.id);

        } else if constexpr (std::is_same_v<T, ex::EvAckCancel>) {
            dst.push_back('C'); wr(dst, e.id);

        } else if constexpr (std::is_same_v<T, ex::EvReject>) {
            dst.push_back('R'); wr(dst, e.id);

        } else if constexpr (std::is_same_v<T, ex::EvTrade>) {
            dst.push_back('T');
            wr(dst, e.t.maker);
            wr(dst, e.t.taker);
            wr(dst, e.t.price);
            wr(dst, e.t.qty);
        }

    }, ev);
}

} // namespace wire

