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

CallError MatchingEngine::begin(const Command& command) {
    if (active()) return CallError::Busy;
    const auto max_seq = std::numeric_limits<Sequence>::max();
    if (command_seq_ == max_seq || event_capacity_ > max_seq - event_seq_) {
        return CallError::SequenceExhausted;
    }

    current_ = command;
    ++command_seq_;
    rejection_ = validate(command);
    remaining_ = filled_ = resting_ = cancelled_ = 0;
    if (rejection_ == RejectReason::None) {
        if (const auto* limit = std::get_if<LimitOrder>(&command.payload)) {
            remaining_ = limit->qty;
        } else if (const auto* market = std::get_if<MarketOrder>(&command.payload)) {
            remaining_ = market->qty;
        }
    }
    phase_ = Phase::Admission;
    return CallError::None;
}

bool MatchingEngine::active() const noexcept { return phase_ != Phase::Idle; }

Event MatchingEngine::make_event(EventKind kind) {
    Event event{};
    event.kind = kind;
    event.command_kind = command_kind(current_);
    event.command_seq = command_seq_;
    event.event_seq = ++event_seq_;
    event.client = current_.client;
    event.request = current_.request;
    event.order_id = order_id(current_);
    return event;
}

bool MatchingEngine::next(Event& output) {
    if (!active()) return false;
    if (phase_ == Phase::Admission) {
        if (rejection_ != RejectReason::None) {
            output = make_event(EventKind::Rejected);
            output.reject_reason = rejection_;
            phase_ = Phase::Complete;
        } else {
            output = make_event(EventKind::Accepted);
            phase_ = Phase::Execution;
        }
        return true;
    }
    if (phase_ == Phase::Complete) {
        output = make_event(EventKind::CommandComplete);
        output.completion = rejection_ == RejectReason::None
            ? CompletionStatus::Accepted : CompletionStatus::Rejected;
        output.filled_qty = filled_;
        output.resting_qty = resting_;
        output.cancelled_qty = cancelled_;
        phase_ = Phase::Idle;
        return true;
    }

    assert(phase_ == Phase::Execution);
    const OrderId id = order_id(current_);
    if (std::holds_alternative<CancelOrder>(current_.payload)) {
        cancelled_ = book_.erase_resting(id);
        output = make_event(EventKind::Cancelled);
        output.qty = cancelled_;
        output.cancel_reason = CancelReason::UserCancel;
        phase_ = Phase::Complete;
        return true;
    }

    const auto* limit = std::get_if<LimitOrder>(&current_.payload);
    const Side side = limit ? limit->side : std::get<MarketOrder>(current_.payload).side;
    assert(remaining_ > 0);
    const Order* next_maker = book_.best_opposite(side);
    const bool crosses = next_maker && (!limit ||
        (side == Side::Buy ? next_maker->price <= limit->price : next_maker->price >= limit->price));
    if (crosses) {
        // apply_fill may erase both the maker node and its price level.
        const Order maker = *next_maker;
        const Quantity qty = std::min(remaining_, maker.remaining);
        book_.apply_fill(maker.id, qty);
        remaining_ -= qty;
        filled_ += qty; // Bounded by the validated submitted quantity.
        output = make_event(EventKind::Trade);
        output.price = maker.price;
        output.qty = qty;
        output.maker_id = maker.id;
        output.taker_id = id;
        output.maker_client = maker.owner;
        output.taker_client = current_.client;
        output.maker_arrival_seq = maker.arrival_seq;
        output.taker_arrival_seq = command_seq_;
        if (remaining_ == 0) phase_ = Phase::Complete;
        return true;
    }

    if (limit) {
        book_.insert_resting({id, current_.client, side, limit->price, remaining_, command_seq_});
        resting_ = remaining_;
        output = make_event(EventKind::Rested);
        output.side = side;
        output.price = limit->price;
        output.qty = remaining_;
        output.arrival_seq = command_seq_;
    } else {
        cancelled_ = remaining_;
        output = make_event(EventKind::Cancelled);
        output.qty = remaining_;
        output.cancel_reason = CancelReason::IocRemainder;
    }
    remaining_ = 0;
    phase_ = Phase::Complete;
    return true;
}

ProcessResult MatchingEngine::process(const Command& command, std::span<Event> output) {
    if (output.size() < event_capacity_) return {ProcessStatus::OutputBufferTooSmall, 0};
    if (active()) throw std::logic_error("process requires an idle engine");
    if (begin(command) == CallError::SequenceExhausted) {
        return {ProcessStatus::SequenceExhausted, 0};
    }
    std::size_t count = 0;
    while (active()) {
        assert(count < output.size());
        next(output[count++]);
    }
    return {ProcessStatus::Processed, count};
}

TopOfBook MatchingEngine::top_of_book() const noexcept { return book_.top_of_book(); }

BookSnapshot MatchingEngine::snapshot() const { return book_.snapshot(); }

void MatchingEngine::check_invariants() const {
    book_.check_invariants();
    if (book_.size() > config_.max_live_orders) throw std::logic_error("book exceeds configured capacity");
    const Order* bid = book_.best_opposite(Side::Sell);
    const Order* ask = book_.best_opposite(Side::Buy);
    if (bid && ask && bid->price >= ask->price) throw std::logic_error("crossed resting book");
}

}
