#pragma once
#include "llmatch/types.hpp"
#include <variant>

namespace llmatch {
enum class CommandKind : std::uint8_t { Limit, Market, Cancel };
struct LimitOrder {
    OrderId id;
    Side side;
    Price price;
    Quantity qty;
    bool operator==(const LimitOrder&) const = default;
};
struct MarketOrder {
    OrderId id;
    Side side;
    Quantity qty;
    bool operator==(const MarketOrder&) const = default;
};
struct CancelOrder {
    OrderId id;
    bool operator==(const CancelOrder&) const = default;
};
struct Command {
    ClientId client;
    RequestId request;
    std::variant<LimitOrder, MarketOrder, CancelOrder> payload;
    bool operator==(const Command&) const = default;
};
inline CommandKind command_kind(const Command& command) {
    return static_cast<CommandKind>(command.payload.index());
}
inline OrderId order_id(const Command& command) {
    return std::visit([](const auto& order) { return order.id; }, command.payload);
}
}
