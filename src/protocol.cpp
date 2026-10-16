#include "llmatch/protocol.hpp"

#include <bit>
#include <type_traits>

namespace llmatch::protocol {
namespace {

constexpr std::size_t payload_size(MessageType type) noexcept {
    switch (type) {
        case MessageType::Welcome: return 4;
        case MessageType::Limit: return 33;
        case MessageType::Market: return 25;
        case MessageType::Cancel: return 16;
        case MessageType::BusinessEvent: return 130;
        case MessageType::Bbo: return 50;
    }
    return 0;
}
static_assert(header_size + payload_size(MessageType::BusinessEvent) <= max_frame_size);

// Bounds are established once by the fixed frame type/length check. These
// helpers operate only on that validated payload, without repeated checks.
class Reader {
public:
    explicit Reader(std::span<const std::uint8_t> bytes) : bytes_(bytes) {}
    template<class T> T integer() noexcept {
        static_assert(std::is_unsigned_v<T>);
        T value{};
        for (std::size_t i = 0; i < sizeof(T); ++i) {
            value = static_cast<T>((static_cast<std::uint64_t>(value) << 8) | bytes_[offset_++]);
        }
        return value;
    }
    template<class E> E enumeration() noexcept {
        return static_cast<E>(integer<std::underlying_type_t<E>>());
    }
    Price price() noexcept { return std::bit_cast<Price>(integer<std::uint64_t>()); }
private:
    std::span<const std::uint8_t> bytes_;
    std::size_t offset_{};
};

class Writer {
public:
    explicit Writer(Frame& frame) : frame_(frame) {}
    template<class T> void integer(T value) noexcept {
        static_assert(std::is_unsigned_v<T>);
        for (std::size_t i = sizeof(T); i != 0; --i) {
            frame_.storage[frame_.size++] = static_cast<std::uint8_t>(value >> ((i - 1) * 8));
        }
    }
    template<class E> void enumeration(E value) noexcept {
        integer(static_cast<std::underlying_type_t<E>>(value));
    }
    void price(Price value) noexcept { integer(std::bit_cast<std::uint64_t>(value)); }
private:
    Frame& frame_;
};

void header(Writer& writer, MessageType type) noexcept {
    writer.integer(version);
    writer.enumeration(type);
    writer.integer(static_cast<std::uint32_t>(payload_size(type)));
}

FrameInfo exact_frame(std::span<const std::uint8_t> bytes) {
    const auto info = inspect(bytes);
    if (info.status == FrameStatus::Invalid) throw ProtocolError(info.error);
    if (info.status == FrameStatus::NeedMore) throw ProtocolError(Error::IncompleteFrame);
    if (bytes.size() != info.frame_size) throw ProtocolError(Error::TrailingBytes);
    return info;
}

Command request(Reader& reader, MessageType type, ClientId client) {
    const auto request_id = reader.integer<RequestId>();
    const auto order = reader.integer<OrderId>();
    if (type == MessageType::Cancel) return {client, request_id, CancelOrder{order}};
    const auto side = reader.enumeration<Side>();
    if (type == MessageType::Market) return {client, request_id, MarketOrder{order, side, reader.integer<Quantity>()}};
    const auto price = reader.price();
    return {client, request_id, LimitOrder{order, side, price, reader.integer<Quantity>()}};
}

void write_event(Writer& w, const Event& e) noexcept {
    w.enumeration(e.kind);
    w.enumeration(e.command_kind);
    w.integer(e.command_seq);
    w.integer(e.event_seq);
    w.integer(e.client);
    w.integer(e.request);
    w.integer(e.order_id);
    w.enumeration(e.reject_reason);
    w.enumeration(e.cancel_reason);
    w.enumeration(e.completion);
    w.enumeration(e.side);
    w.price(e.price);
    w.integer(e.qty);
    w.integer(e.arrival_seq);
    w.integer(e.maker_id);
    w.integer(e.taker_id);
    w.integer(e.maker_client);
    w.integer(e.taker_client);
    w.integer(e.maker_arrival_seq);
    w.integer(e.taker_arrival_seq);
    w.integer(e.filled_qty);
    w.integer(e.resting_qty);
    w.integer(e.cancelled_qty);
}

Event read_event(Reader& r) {
    Event e{};
    e.kind = r.enumeration<EventKind>();
    e.command_kind = r.enumeration<CommandKind>();
    e.command_seq = r.integer<Sequence>();
    e.event_seq = r.integer<Sequence>();
    e.client = r.integer<ClientId>();
    e.request = r.integer<RequestId>();
    e.order_id = r.integer<OrderId>();
    e.reject_reason = r.enumeration<RejectReason>();
    e.cancel_reason = r.enumeration<CancelReason>();
    e.completion = r.enumeration<CompletionStatus>();
    e.side = r.enumeration<Side>();
    e.price = r.price();
    e.qty = r.integer<Quantity>();
    e.arrival_seq = r.integer<Sequence>();
    e.maker_id = r.integer<OrderId>();
    e.taker_id = r.integer<OrderId>();
    e.maker_client = r.integer<ClientId>();
    e.taker_client = r.integer<ClientId>();
    e.maker_arrival_seq = r.integer<Sequence>();
    e.taker_arrival_seq = r.integer<Sequence>();
    e.filled_qty = r.integer<Quantity>();
    e.resting_qty = r.integer<Quantity>();
    e.cancelled_qty = r.integer<Quantity>();
    // Response enums are protocol values. Request Side is intentionally not
    // checked here: invalid request values must reach Matching's business rules.
    if (e.kind > EventKind::CommandComplete || e.command_kind > CommandKind::Cancel ||
        e.reject_reason > RejectReason::CapacityExceeded || e.cancel_reason > CancelReason::IocRemainder ||
        e.completion > CompletionStatus::Rejected || e.side > Side::Sell) {
        throw ProtocolError(Error::InvalidField);
    }
    return e;
}

} // namespace

const char* error_name(Error error) noexcept {
    switch (error) {
        case Error::None: return "none";
        case Error::UnsupportedVersion: return "unsupported_version";
        case Error::UnknownMessageType: return "unknown_message_type";
        case Error::InvalidPayloadLength: return "invalid_payload_length";
        case Error::FrameTooLarge: return "frame_too_large";
        case Error::IncompleteFrame: return "incomplete_frame";
        case Error::TrailingBytes: return "trailing_bytes";
        case Error::UnexpectedMessageType: return "unexpected_message_type";
        case Error::InvalidField: return "invalid_field";
    }
    return "unknown_protocol_error";
}

ProtocolError::ProtocolError(Error error) : std::runtime_error(error_name(error)), error_(error) {}

bool is_request(MessageType type) noexcept {
    return type == MessageType::Limit || type == MessageType::Market || type == MessageType::Cancel;
}

FrameInfo inspect(std::span<const std::uint8_t> bytes) noexcept {
    if (bytes.size() < header_size) return {FrameStatus::NeedMore, {}, header_size, Error::None};
    Reader reader(bytes.first(header_size));
    const auto wire_version = reader.integer<std::uint16_t>();
    const auto type = reader.enumeration<MessageType>();
    const auto length = reader.integer<std::uint32_t>();
    if (wire_version != version) return {FrameStatus::Invalid, type, 0, Error::UnsupportedVersion};
    const auto expected = payload_size(type);
    if (expected == 0) return {FrameStatus::Invalid, type, 0, Error::UnknownMessageType};
    if (length > max_frame_size - header_size) return {FrameStatus::Invalid, type, 0, Error::FrameTooLarge};
    if (length != expected) return {FrameStatus::Invalid, type, 0, Error::InvalidPayloadLength};
    const auto full_size = header_size + expected;
    return {bytes.size() < full_size ? FrameStatus::NeedMore : FrameStatus::Ready, type, full_size, Error::None};
}

Frame encode(const Welcome& message) {
    Frame result;
    Writer writer(result);
    header(writer, MessageType::Welcome);
    writer.integer(message.client);
    return result;
}

Frame encode(const Command& message) {
    Frame result;
    Writer writer(result);
    std::visit([&](const auto& order) {
        using T = std::decay_t<decltype(order)>;
        constexpr MessageType type = std::is_same_v<T, LimitOrder> ? MessageType::Limit :
            std::is_same_v<T, MarketOrder> ? MessageType::Market : MessageType::Cancel;
        header(writer, type);
        writer.integer(message.request);
        writer.integer(order.id);
        if constexpr (!std::is_same_v<T, CancelOrder>) writer.enumeration(order.side);
        if constexpr (std::is_same_v<T, LimitOrder>) writer.price(order.price);
        if constexpr (!std::is_same_v<T, CancelOrder>) writer.integer(order.qty);
    }, message.payload);
    return result;
}

Frame encode(const Event& message) {
    Frame result;
    Writer writer(result);
    header(writer, MessageType::BusinessEvent);
    write_event(writer, message);
    return result;
}

Frame encode(const llmatch::Bbo& message) {
    Frame result;
    Writer writer(result);
    header(writer, MessageType::Bbo);
    writer.integer(static_cast<std::uint8_t>(message.bid_present));
    writer.integer(static_cast<std::uint8_t>(message.ask_present));
    writer.price(message.bid_price);
    writer.integer(message.bid_qty);
    writer.price(message.ask_price);
    writer.integer(message.ask_qty);
    writer.integer(message.command_seq);
    writer.integer(message.as_of_event_seq);
    return result;
}

Decoded decode(std::span<const std::uint8_t> frame, ClientId request_client) {
    const auto info = exact_frame(frame);
    Reader reader(frame.subspan(header_size));
    if (is_request(info.type)) return request(reader, info.type, request_client);
    if (info.type == MessageType::Welcome) return Welcome{reader.integer<ClientId>()};
    if (info.type == MessageType::BusinessEvent) return read_event(reader);
    const auto bid_present = reader.integer<std::uint8_t>();
    const auto ask_present = reader.integer<std::uint8_t>();
    if (bid_present > 1 || ask_present > 1) throw ProtocolError(Error::InvalidField);
    llmatch::Bbo bbo;
    bbo.bid_present = bid_present != 0;
    bbo.ask_present = ask_present != 0;
    bbo.bid_price = reader.price();
    bbo.bid_qty = reader.integer<Quantity>();
    bbo.ask_price = reader.price();
    bbo.ask_qty = reader.integer<Quantity>();
    bbo.command_seq = reader.integer<Sequence>();
    bbo.as_of_event_seq = reader.integer<Sequence>();
    return bbo;
}

Command decode_request(std::span<const std::uint8_t> frame, ClientId request_client) {
    const auto info = exact_frame(frame);
    if (!is_request(info.type)) throw ProtocolError(Error::UnexpectedMessageType);
    Reader reader(frame.subspan(header_size));
    return request(reader, info.type, request_client);
}

} // namespace llmatch::protocol
