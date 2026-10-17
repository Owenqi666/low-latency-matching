#include "llmatch/order_book.hpp"

#include <cassert>
#include <limits>
#include <stdexcept>

namespace llmatch {

OrderBook::OrderBook(std::size_t capacity)
    : slots_(capacity), free_head_(capacity == 0 ? no_slot : 0) {
    by_id_.max_load_factor(0.75F);
    by_id_.reserve(capacity);
    for (SlotIndex index = 0; index < capacity; ++index) {
        slots_[index].next = index + 1 < capacity ? index + 1 : no_slot;
    }
}

std::size_t OrderBook::size() const noexcept { return by_id_.size(); }

const Order* OrderBook::find(OrderId id) const {
    const auto entry = by_id_.find(id);
    return entry == by_id_.end() ? nullptr : &slots_[entry->second.order].order;
}

const Order* OrderBook::best_opposite(Side taker_side) const {
    assert(taker_side == Side::Buy || taker_side == Side::Sell);
    if (taker_side == Side::Buy) {
        return asks_.empty() ? nullptr : &slots_[asks_.begin()->second.head].order;
    }
    return bids_.empty() ? nullptr : &slots_[bids_.rbegin()->second.head].order;
}

void OrderBook::insert_resting(const Order& order) {
    assert(order.remaining > 0);
    assert(order.side == Side::Buy || order.side == Side::Sell);
    assert(!by_id_.contains(order.id));
    assert(free_head_ != no_slot);
    auto& levels = order.side == Side::Buy ? bids_ : asks_;
    auto [level, created] = levels.try_emplace(order.price);
    (void)created;
    auto& value = level->second;
    if (order.remaining > std::numeric_limits<Quantity>::max() - value.total_qty) {
        throw std::overflow_error("price level quantity overflow");
    }
    const SlotIndex index = free_head_;
    by_id_.emplace(order.id, Locator{order.side, level, index});
    auto& slot = slots_[index];
    free_head_ = slot.next;
    slot.order = order;
    slot.previous = value.tail;
    slot.next = no_slot;
    if (value.tail == no_slot) value.head = index;
    else slots_[value.tail].next = index;
    value.tail = index;
    value.total_qty += order.remaining;
}

void OrderBook::erase_node(Index::iterator entry) {
    // Copy before erasing the index. The released slot can immediately be reused;
    // callers must not retain its order view across this operation.
    const Locator location = entry->second;
    auto& levels = location.side == Side::Buy ? bids_ : asks_;
    auto& level = location.level->second;
    auto& slot = slots_[location.order];
    if (slot.previous == no_slot) level.head = slot.next;
    else slots_[slot.previous].next = slot.next;
    if (slot.next == no_slot) level.tail = slot.previous;
    else slots_[slot.next].previous = slot.previous;
    by_id_.erase(entry);
    slot.previous = no_slot;
    slot.next = free_head_;
    free_head_ = location.order;
    if (level.head == no_slot) {
        assert(level.tail == no_slot && level.total_qty == 0);
        levels.erase(location.level);
    }
}

void OrderBook::apply_fill(OrderId id, Quantity qty) {
    const auto entry = by_id_.find(id);
    assert(entry != by_id_.end());
    auto& order = slots_[entry->second.order].order;
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
    const Quantity qty = slots_[entry->second.order].order.remaining;
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
    const auto append = [&](std::vector<LevelSnapshot>& output, Price price, const PriceLevel& level) {
        output.push_back({price, level.total_qty, {}});
        for (SlotIndex index = level.head; index != no_slot; index = slots_[index].next) {
            output.back().orders.push_back(slots_[index].order);
        }
    };
    for (auto it = bids_.rbegin(); it != bids_.rend(); ++it) append(result.bids, it->first, it->second);
    for (const auto& [price, level] : asks_) append(result.asks, price, level);
    return result;
}

void OrderBook::check_invariants() const {
    // This complete scan is explicit validation, never part of command processing.
    std::vector<bool> visited(slots_.size());
    std::size_t count = 0;
    const auto check_side = [&](const Levels& levels, Side side) {
        for (auto level_it = levels.begin(); level_it != levels.end(); ++level_it) {
            const auto& [price, level] = *level_it;
            if (level.head == no_slot || level.tail == no_slot) {
                throw std::logic_error("empty price level");
            }
            Quantity total = 0;
            Sequence previous_arrival = 0;
            SlotIndex previous_slot = no_slot;
            for (SlotIndex index = level.head; index != no_slot; index = slots_[index].next) {
                if (index >= slots_.size() || visited[index]) {
                    throw std::logic_error("invalid or repeated FIFO slot");
                }
                visited[index] = true;
                const auto& slot = slots_[index];
                const auto& order = slot.order;
                if (slot.previous != previous_slot || order.id == 0 || order.owner == 0 ||
                    order.side != side || order.price != price || order.price <= 0 ||
                    order.remaining == 0 || order.arrival_seq <= previous_arrival) {
                    throw std::logic_error("invalid resting order or FIFO link");
                }
                const auto found = by_id_.find(order.id);
                if (found == by_id_.end() || found->second.side != side ||
                    found->second.level != level_it || found->second.order != index) {
                    throw std::logic_error("order index does not point to its FIFO slot");
                }
                if (order.remaining > std::numeric_limits<Quantity>::max() - total) {
                    throw std::logic_error("price level total overflow");
                }
                total += order.remaining;
                previous_arrival = order.arrival_seq;
                previous_slot = index;
                ++count;
            }
            if (previous_slot != level.tail || total != level.total_qty) {
                throw std::logic_error("incorrect price level tail or total");
            }
        }
    };
    check_side(bids_, Side::Buy);
    check_side(asks_, Side::Sell);
    if (count != by_id_.size()) {
        throw std::logic_error("order index size differs from FIFO slot count");
    }
    std::size_t free_count = 0;
    for (SlotIndex index = free_head_; index != no_slot; index = slots_[index].next) {
        if (index >= slots_.size() || visited[index] || slots_[index].previous != no_slot) {
            throw std::logic_error("invalid, repeated or active free slot");
        }
        visited[index] = true;
        ++free_count;
    }
    if (count + free_count != slots_.size()) {
        throw std::logic_error("active and free slots do not cover capacity");
    }
}

}
