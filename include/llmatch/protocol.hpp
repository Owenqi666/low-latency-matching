#pragma once

#include "llmatch/event.hpp"
#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <stdexcept>
#include <variant>

namespace llmatch {

struct Bbo {
    bool bid_present{};
    bool ask_present{};
    Price bid_price{};
    Quantity bid_qty{};
    Price ask_price{};
    Quantity ask_qty{};
    Sequence command_seq{};
    Sequence as_of_event_seq{};
    bool operator==(const Bbo&) const = default;
};

namespace protocol {

inline constexpr std::uint16_t version = 1;
inline constexpr std::size_t header_size = 8;
inline constexpr std::size_t max_frame_size = 256;

enum class MessageType : std::uint16_t {
    Welcome = 1, Limit = 2, Market = 3, Cancel = 4, BusinessEvent = 5, Bbo = 6
};

enum class Error {
    None, UnsupportedVersion, UnknownMessageType, InvalidPayloadLength,
    FrameTooLarge, IncompleteFrame, TrailingBytes, UnexpectedMessageType,
    InvalidField
};

const char* error_name(Error error) noexcept;

class ProtocolError : public std::runtime_error {
public:
    explicit ProtocolError(Error error);
    Error code() const noexcept { return error_; }
private:
    Error error_;
};

struct Welcome {
    ClientId client{};
    bool operator==(const Welcome&) const = default;
};

struct Frame {
    std::array<std::uint8_t, max_frame_size> storage{};
    std::size_t size{};
    std::span<const std::uint8_t> bytes() const noexcept { return {storage.data(), size}; }
};

enum class FrameStatus { NeedMore, Ready, Invalid };
struct FrameInfo {
    FrameStatus status{};
    MessageType type{};
    std::size_t frame_size{};
    Error error{};
};

// NeedMore reports 8 until the header is complete, then the full frame length.
// Ready describes only the first frame; a buffer may contain subsequent frames.
FrameInfo inspect(std::span<const std::uint8_t> bytes) noexcept;
bool is_request(MessageType type) noexcept;

Frame encode(const Welcome& message);
Frame encode(const Command& message); // ClientId is not transmitted.
Frame encode(const Event& message);
Frame encode(const llmatch::Bbo& message);

using Decoded = std::variant<Welcome, Command, Event, llmatch::Bbo>;
// Decoders require exactly one complete frame and throw ProtocolError on error.
// request_client is assigned by Gateway, never obtained from request bytes.
Decoded decode(std::span<const std::uint8_t> frame, ClientId request_client = 0);
Command decode_request(std::span<const std::uint8_t> frame, ClientId request_client);

} // namespace protocol
} // namespace llmatch
