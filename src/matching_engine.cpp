#include "llmatch/matching_engine.hpp"

#include <algorithm>
#include <cassert>
#include <limits>
#include <stdexcept>

namespace llmatch {
namespace {
std::size_t validate_config(EngineConfig config) {
    const auto max_quantity = std::numeric_limits<Quantity>::max();
    const auto max_size = std::numeric_limits<std::size_t>::max();
    if (config.max_live_orders == 0 || config.max_price <= 0 || config.max_order_qty == 0) {
        throw std::invalid_argument("capacity, max_price and max_order_qty must be positive");
    }
    if (config.max_live_orders > max_quantity / config.max_order_qty) {
        throw std::invalid_argument("aggregate book quantity is not representable");
    }
    if (config.max_live_orders > max_size - 4 ||
        config.max_live_orders + 4 > max_size / sizeof(Event)) {
        throw std::invalid_argument("event buffer capacity is not representable");
    }
    return config.max_live_orders + 4;
}
}

MatchingEngine::MatchingEngine(EngineConfig config)
    : config_(config), event_capacity_(validate_config(config)), book_(config.max_live_orders) {}

std::size_t MatchingEngine::required_event_capacity() const noexcept { return event_capacity_; }

RejectReason MatchingEngine::validate(const Command& command) const {
    if (command.client == 0) return RejectReason::InvalidClientId;
    if (command.request == 0) return RejectReason::InvalidRequestId;
    const auto id = order_id(command);
    if (id == 0) return RejectReason::InvalidOrderId;

    if (std::holds_alternative<CancelOrder>(command.payload)) {
        const Order* order = book_.find(id);
        if (order == nullptr) return RejectReason::UnknownOrder;
        return order->owner != command.client ? RejectReason::NotOwner : RejectReason::None;
    }

    const auto* limit = std::get_if<LimitOrder>(&command.payload);
    const auto side = limit ? limit->side : std::get<MarketOrder>(command.payload).side;
    const auto qty = limit ? limit->qty : std::get<MarketOrder>(command.payload).qty;
    if (side != Side::Buy && side != Side::Sell) return RejectReason::InvalidSide;
    if (qty == 0 || qty > config_.max_order_qty) return RejectReason::InvalidQuantity;
    if (limit && (limit->price <= 0 || limit->price > config_.max_price)) {
        return RejectReason::InvalidPrice;
    }
    if (book_.find(id)) return RejectReason::DuplicateOrder;
    if (limit && book_.size() == config_.max_live_orders) return RejectReason::CapacityExceeded;
    return RejectReason::None;
}

ProcessResult MatchingEngine::process(const Command& command, std::span<Event> output) {
    if (output.size() < event_capacity_) return {ProcessStatus::OutputBufferTooSmall, 0};
    const auto max_seq = std::numeric_limits<Sequence>::max();
    if (command_seq_ == max_seq || event_capacity_ > max_seq - event_seq_) {
        return {ProcessStatus::SequenceExhausted, 0};
    }

    ++command_seq_;
    std::size_t count = 0;
    const CommandKind kind = command_kind(command);
    const OrderId id = order_id(command);
    const auto emit = [&](EventKind event_kind) -> Event& {
        assert(count < output.size());
        Event& event = output[count++];
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

    const RejectReason rejection = validate(command);
    if (rejection != RejectReason::None) {
        emit(EventKind::Rejected).reject_reason = rejection;
        emit(EventKind::CommandComplete).completion = CompletionStatus::Rejected;
        return {ProcessStatus::Processed, count};
    }

    emit(EventKind::Accepted);
    Quantity filled = 0;
    Quantity resting = 0;
    Quantity cancelled = 0;
    if (kind == CommandKind::Cancel) {
        cancelled = book_.erase_resting(id);
        auto& event = emit(EventKind::Cancelled);
        event.qty = cancelled;
        event.cancel_reason = CancelReason::UserCancel;
    } else {
        const auto* limit = std::get_if<LimitOrder>(&command.payload);
        const Side side = limit ? limit->side : std::get<MarketOrder>(command.payload).side;
        Quantity remaining = limit ? limit->qty : std::get<MarketOrder>(command.payload).qty;
        while (remaining > 0) {
            const Order* next = book_.best_opposite(side);
            if (next == nullptr) break;
            if (limit && (side == Side::Buy ? next->price > limit->price : next->price < limit->price)) {
                break;
            }
            // apply_fill may erase both the maker node and its price level.
            const Order maker = *next;
            const Quantity qty = std::min(remaining, maker.remaining);
            book_.apply_fill(maker.id, qty);
            remaining -= qty;
            filled += qty; // Bounded by the validated submitted quantity.
            auto& trade = emit(EventKind::Trade);
            trade.price = maker.price;
            trade.qty = qty;
            trade.maker_id = maker.id;
            trade.taker_id = id;
            trade.maker_client = maker.owner;
            trade.taker_client = command.client;
            trade.maker_arrival_seq = maker.arrival_seq;
            trade.taker_arrival_seq = command_seq_;
        }
        if (remaining > 0 && limit) {
            book_.insert_resting({id, command.client, side, limit->price, remaining, command_seq_});
            resting = remaining;
            auto& event = emit(EventKind::Rested);
            event.side = side;
            event.price = limit->price;
            event.qty = remaining;
            event.arrival_seq = command_seq_;
        } else if (remaining > 0) {
            cancelled = remaining;
            auto& event = emit(EventKind::Cancelled);
            event.qty = remaining;
            event.cancel_reason = CancelReason::IocRemainder;
        }
    }
    auto& complete = emit(EventKind::CommandComplete);
    complete.completion = CompletionStatus::Accepted;
    complete.filled_qty = filled;
    complete.resting_qty = resting;
    complete.cancelled_qty = cancelled;
    return {ProcessStatus::Processed, count};
}

BookSnapshot MatchingEngine::snapshot() const { return book_.snapshot(); }

void MatchingEngine::check_invariants() const {
    book_.check_invariants();
    if (book_.size() > config_.max_live_orders) throw std::logic_error("book exceeds configured capacity");
    const Order* bid = book_.best_opposite(Side::Sell);
    const Order* ask = book_.best_opposite(Side::Buy);
    if (bid && ask && bid->price >= ask->price) throw std::logic_error("crossed resting book");
}

}
