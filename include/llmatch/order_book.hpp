#pragma once

#include "llmatch/snapshot.hpp"

#include <limits>
#include <map>
#include <unordered_map>
#include <vector>

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

// Owns price levels, fixed FIFO slots and their index. Business admission belongs
// to MatchingEngine. Mutators receive validated orders within the fixed capacity.
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
    using SlotIndex = std::size_t;
    static constexpr SlotIndex no_slot = std::numeric_limits<SlotIndex>::max();
    struct Slot {
        Order order{};
        SlotIndex previous{no_slot};
        SlotIndex next{no_slot}; // Next FIFO slot when active; next free slot otherwise.
    };
    struct PriceLevel {
        Quantity total_qty{};
        SlotIndex head{no_slot};
        SlotIndex tail{no_slot};
    };
    using Levels = std::map<Price, PriceLevel>;
    struct Locator {
        Side side;
        Levels::iterator level;
        SlotIndex order;
    };
    using Index = std::unordered_map<OrderId, Locator>;

    // Removes a slot whose quantity has already been deducted from its level.
    void erase_node(Index::iterator entry);

    Levels bids_;
    Levels asks_;
    Index by_id_;
    std::vector<Slot> slots_;
    SlotIndex free_head_;
};

}
