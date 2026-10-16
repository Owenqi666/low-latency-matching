#pragma once

#include <cstddef>
#include <cstdint>

namespace llmatch {
using Price = std::int64_t;
using Quantity = std::uint64_t;
using ClientId = std::uint32_t;
using RequestId = std::uint64_t;
using OrderId = std::uint64_t;
using Sequence = std::uint64_t;

enum class Side : std::uint8_t { Buy, Sell };

struct EngineConfig {
    std::size_t max_live_orders;
    Price max_price;
    Quantity max_order_qty;
    bool operator==(const EngineConfig&) const = default;
};
}
