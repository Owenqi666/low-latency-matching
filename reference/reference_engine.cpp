#include "reference_engine.hpp"

#include <algorithm>
#include <cassert>
#include <limits>
#include <stdexcept>
#include <unordered_set>

namespace llmatch {

ReferenceEngine::ReferenceEngine(EngineConfig config) : config_(config) {
    const auto max_size = std::numeric_limits<std::size_t>::max();
    if (config.max_live_orders == 0 || config.max_price <= 0 || config.max_order_qty == 0 ||
        config.max_live_orders > std::numeric_limits<Quantity>::max() / config.max_order_qty ||
        config.max_live_orders > max_size - 4 ||
        config.max_live_orders + 4 > max_size / sizeof(Event)) {
        throw std::invalid_argument("invalid reference engine configuration");
    }
}

std::size_t ReferenceEngine::required_event_capacity() const {
    return config_.max_live_orders + 4;
}

ProcessResult ReferenceEngine::process(const Command& command, std::span<Event> output) {
    const auto capacity = required_event_capacity();
    if (output.size() < capacity) {
        return {ProcessStatus::OutputBufferTooSmall, 0};
    }
    const auto last_sequence = std::numeric_limits<Sequence>::max();
    if (command_seq_ == last_sequence || last_sequence - event_seq_ < capacity) {
        return {ProcessStatus::SequenceExhausted, 0};
    }

    ++command_seq_;
    std::size_t emitted = 0;
    const auto id = order_id(command);
    const auto kind = command_kind(command);
    const auto emit = [&](EventKind event_kind) -> Event& {
        auto& event = output[emitted++];
        event = Event{};
        event.kind = event_kind;
        event.command_kind = kind;
        event.command_seq = command_seq_;
        event.event_seq = ++event_seq_;
        event.client = command.client;
        event.request = command.request;
        event.order_id = id;
        return event;
    };

    const auto* limit = std::get_if<LimitOrder>(&command.payload);
    const auto* market = std::get_if<MarketOrder>(&command.payload);
    const bool is_new = limit != nullptr || market != nullptr;
    const Side side = limit ? limit->side : market ? market->side : Side::Buy;
    const Quantity submitted = limit ? limit->qty : market ? market->qty : 0;
    const auto existing = std::find_if(orders_.begin(), orders_.end(),
                                      [id](const Order& order) { return order.id == id; });

    RejectReason reject = RejectReason::None;
    if (command.client == 0) reject = RejectReason::InvalidClientId;
    else if (command.request == 0) reject = RejectReason::InvalidRequestId;
    else if (id == 0) reject = RejectReason::InvalidOrderId;
    else if (is_new && side != Side::Buy && side != Side::Sell) reject = RejectReason::InvalidSide;
    else if (is_new && (submitted == 0 || submitted > config_.max_order_qty)) reject = RejectReason::InvalidQuantity;
    else if (limit && (limit->price <= 0 || limit->price > config_.max_price)) reject = RejectReason::InvalidPrice;
    else if (is_new && existing != orders_.end()) reject = RejectReason::DuplicateOrder;
    else if (!is_new && existing == orders_.end()) reject = RejectReason::UnknownOrder;
    else if (!is_new && existing->owner != command.client) reject = RejectReason::NotOwner;
    else if (limit && orders_.size() == config_.max_live_orders) reject = RejectReason::CapacityExceeded;

    if (reject != RejectReason::None) {
        emit(EventKind::Rejected).reject_reason = reject;
        emit(EventKind::CommandComplete).completion = CompletionStatus::Rejected;
        return {ProcessStatus::Processed, emitted};
    }

    emit(EventKind::Accepted);
    if (!is_new) {
        const auto cancelled = existing->remaining;
        // The scan model deliberately discards physical order when deleting.
        // FIFO must be determined by arrival_seq, never by vector position.
        *existing = orders_.back();
        orders_.pop_back();
        auto& event = emit(EventKind::Cancelled);
        event.qty = cancelled;
        event.cancel_reason = CancelReason::UserCancel;
        auto& complete = emit(EventKind::CommandComplete);
        complete.completion = CompletionStatus::Accepted;
        complete.cancelled_qty = cancelled;
        return {ProcessStatus::Processed, emitted};
    }

    Quantity remaining = submitted;
    while (remaining != 0) {
        std::size_t best = orders_.size();
        for (std::size_t index = 0; index < orders_.size(); ++index) {
            const auto& candidate = orders_[index];
            if (candidate.side == side) continue;
            if (limit && (side == Side::Buy ? candidate.price > limit->price : candidate.price < limit->price)) continue;
            if (best == orders_.size() ||
                (side == Side::Buy ? candidate.price < orders_[best].price : candidate.price > orders_[best].price) ||
                (candidate.price == orders_[best].price && candidate.arrival_seq < orders_[best].arrival_seq)) {
                best = index;
            }
        }
        if (best == orders_.size()) break;

        auto& maker = orders_[best];
        const Quantity traded = std::min(remaining, maker.remaining);
        auto& trade = emit(EventKind::Trade);
        trade.maker_id = maker.id;
        trade.taker_id = id;
        trade.maker_client = maker.owner;
        trade.taker_client = command.client;
        trade.maker_arrival_seq = maker.arrival_seq;
        trade.taker_arrival_seq = command_seq_;
        trade.price = maker.price;
        trade.qty = traded;
        assert(traded <= remaining && traded <= maker.remaining);
        remaining -= traded;
        maker.remaining -= traded;
        if (maker.remaining == 0) {
            maker = orders_.back();
            orders_.pop_back();
        }
    }

    if (remaining != 0) {
        if (limit) {
            orders_.push_back({id, command.client, side, limit->price, remaining, command_seq_});
            auto& rested = emit(EventKind::Rested);
            rested.side = side;
            rested.price = limit->price;
            rested.qty = remaining;
            rested.arrival_seq = command_seq_;
        } else {
            auto& cancelled = emit(EventKind::Cancelled);
            cancelled.qty = remaining;
            cancelled.cancel_reason = CancelReason::IocRemainder;
        }
    }
    auto& complete = emit(EventKind::CommandComplete);
    complete.completion = CompletionStatus::Accepted;
    complete.filled_qty = submitted - remaining;
    complete.resting_qty = limit ? remaining : 0;
    complete.cancelled_qty = market ? remaining : 0;
    return {ProcessStatus::Processed, emitted};
}

BookSnapshot ReferenceEngine::snapshot() const {
    auto sorted = orders_;
    std::sort(sorted.begin(), sorted.end(), [](const Order& a, const Order& b) {
        if (a.side != b.side) return a.side == Side::Buy;
        if (a.price != b.price) return a.side == Side::Buy ? a.price > b.price : a.price < b.price;
        return a.arrival_seq < b.arrival_seq;
    });
    BookSnapshot result;
    for (const auto& order : sorted) {
        auto& levels = order.side == Side::Buy ? result.bids : result.asks;
        if (levels.empty() || levels.back().price != order.price) {
            levels.push_back({order.price, 0, {}});
        }
        auto& level = levels.back();
        if (std::numeric_limits<Quantity>::max() - level.total_qty < order.remaining) {
            throw std::logic_error("reference level quantity overflow");
        }
        level.total_qty += order.remaining;
        level.orders.push_back(order);
    }
    return result;
}

void ReferenceEngine::check_invariants() const {
    if (orders_.size() > config_.max_live_orders) throw std::logic_error("reference capacity exceeded");
    std::unordered_set<OrderId> ids;
    std::unordered_set<Sequence> arrivals;
    Price best_bid = 0;
    Price best_ask = std::numeric_limits<Price>::max();
    bool has_ask = false;
    Quantity total = 0;
    for (const auto& order : orders_) {
        if (order.id == 0 || order.owner == 0 || order.arrival_seq == 0 || order.arrival_seq > command_seq_ ||
            !ids.insert(order.id).second || !arrivals.insert(order.arrival_seq).second ||
            (order.side != Side::Buy && order.side != Side::Sell) ||
            order.price <= 0 || order.price > config_.max_price ||
            order.remaining == 0 || order.remaining > config_.max_order_qty) {
            throw std::logic_error("invalid reference live order");
        }
        if (std::numeric_limits<Quantity>::max() - total < order.remaining) {
            throw std::logic_error("reference aggregate quantity overflow");
        }
        total += order.remaining;
        if (order.side == Side::Buy) best_bid = std::max(best_bid, order.price);
        else {
            best_ask = std::min(best_ask, order.price);
            has_ask = true;
        }
    }
    if (has_ask && best_bid >= best_ask) throw std::logic_error("reference crossed book");
}

} // namespace llmatch
