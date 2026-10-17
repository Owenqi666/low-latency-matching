#pragma once

#include "llmatch/snapshot.hpp"

#include <list>
#include <map>
#include <unordered_map>

namespace llmatch {

struct TopOfBook {
    bool bid_present{};
    bool ask_present{};
    Price bid_price{};
    Quantity bid_qty{};
    Price ask_price{};
    Quantity ask_qty{};
    bool operator==(const TopOfBook&) const = default;
};

// Owns price levels, FIFO nodes and their index. Business admission belongs to
// MatchingEngine. Orders supplied to its mutators have already been validated.
class OrderBook {
public:
    explicit OrderBook(std::size_t capacity);
    OrderBook(const OrderBook&) = delete;
    OrderBook& operator=(const OrderBook&) = delete;
    OrderBook(OrderBook&&) = delete;
    OrderBook& operator=(OrderBook&&) = delete;

    std::size_t size() const noexcept;
    // Views remain valid only while the referenced resting order is alive.
    const Order* find(OrderId id) const;
    const Order* best_opposite(Side taker_side) const;
    void insert_resting(const Order& order);
    void apply_fill(OrderId id, Quantity qty);
    Quantity erase_resting(OrderId id);
    TopOfBook top_of_book() const noexcept;
    BookSnapshot snapshot() const;
    void check_invariants() const;

private:
    struct PriceLevel {
        Quantity total_qty{};
        std::list<Order> fifo;
    };
    using Levels = std::map<Price, PriceLevel>;
    struct Locator {
        Side side;
        Levels::iterator level;
        std::list<Order>::iterator order;
    };
    using Index = std::unordered_map<OrderId, Locator>;

    // Removes a node whose quantity has already been deducted from its level.
    void erase_node(Index::iterator entry);

    Levels bids_;
    Levels asks_;
    Index by_id_;
};

}
