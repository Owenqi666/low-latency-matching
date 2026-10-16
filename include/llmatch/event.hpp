#pragma once
#include "llmatch/command.hpp"
#include <type_traits>

namespace llmatch {
enum class EventKind : std::uint8_t { Accepted, Rejected, Trade, Rested, Cancelled, CommandComplete };
enum class RejectReason : std::uint8_t {
    None, InvalidClientId, InvalidRequestId, InvalidOrderId, InvalidSide,
    InvalidQuantity, InvalidPrice, DuplicateOrder, UnknownOrder, NotOwner, CapacityExceeded
};
enum class CancelReason : std::uint8_t { None, UserCancel, IocRemainder };
enum class CompletionStatus : std::uint8_t { None, Accepted, Rejected };

// A fixed-size value record. Fields not used by an event kind remain zero/default.
// Shared representation only: engines independently decide which events to emit.
struct Event {
    EventKind kind{};
    CommandKind command_kind{};
    Sequence command_seq{};
    Sequence event_seq{};
    ClientId client{};
    RequestId request{};
    OrderId order_id{};
    RejectReason reject_reason{};
    CancelReason cancel_reason{};
    CompletionStatus completion{};
    Side side{};
    Price price{};
    Quantity qty{};
    Sequence arrival_seq{};
    OrderId maker_id{};
    OrderId taker_id{};
    ClientId maker_client{};
    ClientId taker_client{};
    Sequence maker_arrival_seq{};
    Sequence taker_arrival_seq{};
    Quantity filled_qty{};
    Quantity resting_qty{};
    Quantity cancelled_qty{};
    bool operator==(const Event&) const = default;
};
static_assert(std::is_trivially_copyable_v<Event>);

enum class ProcessStatus : std::uint8_t { Processed, OutputBufferTooSmall, SequenceExhausted };
struct ProcessResult {
    ProcessStatus status;
    std::size_t event_count;
    bool operator==(const ProcessResult&) const = default;
};
}
