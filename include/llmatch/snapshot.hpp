#pragma once
#include "llmatch/types.hpp"
#include <vector>

namespace llmatch {
struct Order {
    OrderId id;
    ClientId owner;
    Side side;
    Price price;
    Quantity remaining;
    Sequence arrival_seq;
    bool operator==(const Order&) const = default;
};
struct LevelSnapshot {
    Price price;
    Quantity total_qty;
    std::vector<Order> orders;
    bool operator==(const LevelSnapshot&) const = default;
};
struct BookSnapshot {
    std::vector<LevelSnapshot> bids; // Descending price, then FIFO.
    std::vector<LevelSnapshot> asks; // Ascending price, then FIFO.
    bool operator==(const BookSnapshot&) const = default;
};
}
