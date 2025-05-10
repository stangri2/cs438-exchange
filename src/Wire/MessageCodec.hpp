#pragma once

#include "MatchingEngine.hpp"
#include <cstdint>
#include <queue>
#include <string>
#include <vector>

namespace wire {

/* ─────────────── inbound ─────────────── */

/** Feed TCP bytes in `inbuf`; every complete packet is turned into an
 *  `ex::Command` pushed onto `out`.  
 *  Returns the number of bytes consumed; any tail fragment stays in `inbuf`.
 */
std::size_t decode(std::vector<char>& inbuf,
                   std::queue<ex::Command>& out);

/* ─────────────── outbound ────────────── */

/** Append the wire representation of an `ex::Event` to `dst`. */
void encodeEvent(const ex::Event& ev, std::string& dst);

} // namespace wire

