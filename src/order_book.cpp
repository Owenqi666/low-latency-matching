#include "llmatch/order_book.hpp"

#include <cassert>
#include <iterator>
#include <limits>
#include <stdexcept>

namespace llmatch {

OrderBook::OrderBook(std::size_t capacity) {
    by_id_.max_load_factor(0.75F);
    by_id_.reserve(capacity);
}

std::size_t OrderBook::size() const noexcept { return by_id_.size(); }

const Order* OrderBook::find(OrderId id) const {
    const auto entry = by_id_.find(id);
    return entry == by_id_.end() ? nullptr : &*entry->second.order;
}

const Order* OrderBook::best_opposite(Side taker_side) const {
    assert(taker_side == Side::Buy || taker_side == Side::Sell);
    if (taker_side == Side::Buy) {
        return asks_.empty() ? nullptr : &asks_.begin()->second.fifo.front();
    }
    return bids_.empty() ? nullptr : &bids_.rbegin()->second.fifo.front();
}

void OrderBook::insert_resting(const Order& order) {
    assert(order.remaining > 0);
    assert(order.side == Side::Buy || order.side == Side::Sell);
    assert(!by_id_.contains(order.id));
    auto& levels = order.side == Side::Buy ? bids_ : asks_;
    auto [level, created] = levels.try_emplace(order.price);
    (void)created;
    auto& value = level->second;
    if (order.remaining > std::numeric_limits<Quantity>::max() - value.total_qty) {
        throw std::overflow_error("price level quantity overflow");
    }
    value.fifo.push_back(order);
    by_id_.emplace(order.id, Locator{order.side, level, std::prev(value.fifo.end())});
    value.total_qty += order.remaining;
}

void OrderBook::erase_node(Index::iterator entry) {
    // Copy before erasing the index: no locator or order is read after erasure.
    const Locator location = entry->second;
    auto& levels = location.side == Side::Buy ? bids_ : asks_;
    by_id_.erase(entry);
    location.level->second.fifo.erase(location.order);
    if (location.level->second.fifo.empty()) {
        assert(location.level->second.total_qty == 0);
        levels.erase(location.level);
    }
}

void OrderBook::apply_fill(OrderId id, Quantity qty) {
    const auto entry = by_id_.find(id);
    assert(entry != by_id_.end());
    auto& order = *entry->second.order;
    auto& total = entry->second.level->second.total_qty;
    assert(qty > 0 && qty <= order.remaining && qty <= total);
    order.remaining -= qty;
    total -= qty;
    if (order.remaining == 0) {
        erase_node(entry);
    }
}

Quantity OrderBook::erase_resting(OrderId id) {
    const auto entry = by_id_.find(id);
    assert(entry != by_id_.end());
    const Quantity qty = entry->second.order->remaining;
    auto& total = entry->second.level->second.total_qty;
    assert(qty > 0 && qty <= total);
    total -= qty;
    erase_node(entry);
    return qty;
}

TopOfBook OrderBook::top_of_book() const noexcept {
    TopOfBook result;
    if (!bids_.empty()) {
        const auto& [price, level] = *bids_.rbegin();
        result.bid_present = true;
        result.bid_price = price;
        result.bid_qty = level.total_qty;
    }
    if (!asks_.empty()) {
        const auto& [price, level] = *asks_.begin();
        result.ask_present = true;
        result.ask_price = price;
        result.ask_qty = level.total_qty;
    }
    return result;
}

BookSnapshot OrderBook::snapshot() const {
    BookSnapshot result;
    result.bids.reserve(bids_.size());
    result.asks.reserve(asks_.size());
    for (auto it = bids_.rbegin(); it != bids_.rend(); ++it) {
        const auto& [price, level] = *it;
        result.bids.push_back({price, level.total_qty, {level.fifo.begin(), level.fifo.end()}});
    }
    for (const auto& [price, level] : asks_) {
        result.asks.push_back({price, level.total_qty, {level.fifo.begin(), level.fifo.end()}});
    }
    return result;
}

void OrderBook::check_invariants() const {
    std::size_t count = 0;
    const auto check_side = [&](const Levels& levels, Side side) {
        for (auto level_it = levels.begin(); level_it != levels.end(); ++level_it) {
            const auto& [price, level] = *level_it;
            if (level.fifo.empty()) {
                throw std::logic_error("empty price level");
            }
            Quantity total = 0;
            Sequence previous = 0;
            for (auto order_it = level.fifo.begin(); order_it != level.fifo.end(); ++order_it) {
                const Order& order = *order_it;
                if (order.id == 0 || order.owner == 0 || order.side != side ||
                    order.price != price || order.price <= 0 || order.remaining == 0 ||
                    order.arrival_seq <= previous) {
                    throw std::logic_error("invalid resting order or FIFO sequence");
                }
                const auto found = by_id_.find(order.id);
                if (found == by_id_.end() || found->second.side != side ||
                    found->second.level != level_it || found->second.order != order_it) {
                    throw std::logic_error("order index does not point to its FIFO node");
                }
                if (order.remaining > std::numeric_limits<Quantity>::max() - total) {
                    throw std::logic_error("price level total overflow");
                }
                total += order.remaining;
                previous = order.arrival_seq;
                ++count;
            }
            if (total != level.total_qty) {
                throw std::logic_error("incorrect price level total");
            }
        }
    };
    check_side(bids_, Side::Buy);
    check_side(asks_, Side::Sell);
    if (count != by_id_.size()) {
        throw std::logic_error("order index size differs from FIFO node count");
    }
}

}
