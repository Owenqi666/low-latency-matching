#include "llmatch/protocol.hpp"
#include "llmatch/matching_engine.hpp"

#include <gtest/gtest.h>
#include <algorithm>
#include <array>
#include <limits>
#include <string_view>
#include <vector>

namespace llmatch::protocol {
namespace {

std::vector<std::uint8_t> hex(std::string_view text) {
    std::vector<std::uint8_t> bytes;
    unsigned byte{};
    bool high = true;
    for (const char c : text) {
        if (c == ' ' || c == '\n') continue;
        const auto digit = static_cast<unsigned>(c <= '9' ? c - '0' : c - 'a' + 10);
        byte = (byte << 4) | digit;
        if (!high) { bytes.push_back(static_cast<std::uint8_t>(byte)); byte = 0; }
        high = !high;
    }
    return bytes;
}

void expect_bytes(const Frame& actual, std::string_view expected) {
    const auto golden = hex(expected);
    EXPECT_EQ(std::vector(actual.bytes().begin(), actual.bytes().end()), golden);
}

template<class F> void expect_error(F&& action, Error error) {
    try {
        action();
        FAIL() << "Expected ProtocolError " << error_name(error);
    } catch (const ProtocolError& exception) {
        EXPECT_EQ(exception.code(), error);
        EXPECT_STREQ(exception.what(), error_name(error));
    }
}

TEST(Protocol, WelcomeGoldenBytes) {
    const Welcome welcome{0x01020304U};
    const auto frame = encode(welcome);
    expect_bytes(frame, "0001 0001 00000004 01020304");
    EXPECT_EQ(std::get<Welcome>(decode(frame.bytes())), welcome);
}

TEST(Protocol, LimitGoldenBytesPreserveBusinessInvalidValues) {
    // ClientId is deliberately absent. Negative price and side 255 are values
    // for Matching to reject, not malformed wire syntax.
    const Command command{99, 0x0102030405060708ULL,
        LimitOrder{0x1112131415161718ULL, static_cast<Side>(255), -2, 0}};
    const auto frame = encode(command);
    expect_bytes(frame,
        "0001 0002 00000021 0102030405060708 1112131415161718 ff"
        " fffffffffffffffe 0000000000000000");
    auto expected = command;
    expected.client = 42;
    EXPECT_EQ(decode_request(frame.bytes(), 42), expected);
    EXPECT_EQ(std::get<Command>(decode(frame.bytes(), 42)), expected);
}

TEST(Protocol, MarketAndCancelGoldenBytes) {
    const Command market{7, 2, MarketOrder{3, Side::Sell, 4}};
    const auto market_frame = encode(market);
    expect_bytes(market_frame,
        "0001 0003 00000019 0000000000000002 0000000000000003 01 0000000000000004");
    EXPECT_EQ(decode_request(market_frame.bytes(), 7), market);

    const Command cancel{7, 0x0102030405060708ULL, CancelOrder{0x1112131415161718ULL}};
    const auto cancel_frame = encode(cancel);
    expect_bytes(cancel_frame, "0001 0004 00000010 0102030405060708 1112131415161718");
    EXPECT_EQ(decode_request(cancel_frame.bytes(), 7), cancel);
}

TEST(Protocol, BusinessEventGoldenBytesIncludeEveryField) {
    const Event event{
        EventKind::Trade, CommandKind::Market,
        0x0102030405060708ULL, 0x1112131415161718ULL, 0x21222324U,
        0x3132333435363738ULL, 0x4142434445464748ULL,
        RejectReason::CapacityExceeded, CancelReason::IocRemainder,
        CompletionStatus::Rejected, Side::Sell, -2,
        0x5152535455565758ULL, 0x6162636465666768ULL,
        0x7172737475767778ULL, 0x8182838485868788ULL,
        0x91929394U, 0xa1a2a3a4U, 0xb1b2b3b4b5b6b7b8ULL,
        0xc1c2c3c4c5c6c7c8ULL, 0xd1d2d3d4d5d6d7d8ULL,
        0xe1e2e3e4e5e6e7e8ULL, 0xf1f2f3f4f5f6f7f8ULL};
    const auto golden = hex(
        "0001 0005 00000082 02 01 0102030405060708 1112131415161718"
        " 21222324 3132333435363738 4142434445464748 0a 02 02 01"
        " fffffffffffffffe 5152535455565758 6162636465666768"
        " 7172737475767778 8182838485868788 91929394 a1a2a3a4"
        " b1b2b3b4b5b6b7b8 c1c2c3c4c5c6c7c8 d1d2d3d4d5d6d7d8"
        " e1e2e3e4e5e6e7e8 f1f2f3f4f5f6f7f8");
    const auto frame = encode(event);
    ASSERT_EQ(golden.size(), 138U);
    EXPECT_EQ(std::vector(frame.bytes().begin(), frame.bytes().end()), golden);
    EXPECT_EQ(std::get<Event>(decode(golden)), event);
}

TEST(Protocol, BboGoldenBytesAndInitialEmptyQuote) {
    const llmatch::Bbo quote{true, false, 100, 9, 0, 0, 7, 13};
    const auto frame = encode(quote);
    expect_bytes(frame,
        "0001 0006 00000032 01 00 0000000000000064 0000000000000009"
        " 0000000000000000 0000000000000000 0000000000000007 000000000000000d");
    EXPECT_EQ(std::get<llmatch::Bbo>(decode(frame.bytes())), quote);
    const auto empty = encode(llmatch::Bbo{});
    EXPECT_EQ(std::get<llmatch::Bbo>(decode(empty.bytes())), llmatch::Bbo{});
}

TEST(Protocol, RequestValueExtremesAreLosslessAndClientCannotBeSpoofed) {
    constexpr auto maximum = std::numeric_limits<std::uint64_t>::max();
    const std::array<Command, 4> commands{{
        {0xffffffffU, maximum, LimitOrder{maximum, static_cast<Side>(2),
                                       std::numeric_limits<Price>::min(), maximum}},
        {0xffffffffU, 0, LimitOrder{0, Side::Buy, std::numeric_limits<Price>::max(), 0}},
        {0xffffffffU, 0, MarketOrder{0, static_cast<Side>(255), 0}},
        {0xffffffffU, maximum, CancelOrder{maximum}}
    }};
    for (auto command : commands) {
        const auto frame = encode(command);
        command.client = 123;
        EXPECT_EQ(decode_request(frame.bytes(), 123), command);
        EXPECT_EQ(std::get<Command>(decode(frame.bytes(), 123)), command);
    }
}

TEST(Protocol, DecodedBusinessErrorsRetainMatchingRejectionPrecedence) {
    MatchingEngine engine({4, 100, 20});
    std::vector<Event> events(engine.required_event_capacity());
    struct Case { Command command; RejectReason reason; };
    const std::array cases{
        Case{{99, 0, LimitOrder{0, static_cast<Side>(255), -1, 0}}, RejectReason::InvalidRequestId},
        Case{{99, 1, LimitOrder{0, static_cast<Side>(255), -1, 0}}, RejectReason::InvalidOrderId},
        Case{{99, 2, LimitOrder{1, static_cast<Side>(255), -1, 0}}, RejectReason::InvalidSide},
        Case{{99, 3, LimitOrder{1, Side::Buy, -1, 0}}, RejectReason::InvalidQuantity},
        Case{{99, 4, LimitOrder{1, Side::Buy, -1, 1}}, RejectReason::InvalidPrice},
        Case{{99, 5, LimitOrder{1, Side::Buy, 101, 1}}, RejectReason::InvalidPrice},
        Case{{99, 6, MarketOrder{1, static_cast<Side>(2), 0}}, RejectReason::InvalidSide},
        Case{{99, 7, MarketOrder{1, Side::Buy, 21}}, RejectReason::InvalidQuantity},
        Case{{99, 8, CancelOrder{0}}, RejectReason::InvalidOrderId}
    };
    Sequence sequence = 0;
    for (const auto& test : cases) {
        const auto frame = encode(test.command);
        const auto decoded = decode_request(frame.bytes(), 7);
        const auto result = engine.process(decoded, events);
        ASSERT_EQ(result.status, ProcessStatus::Processed);
        ASSERT_EQ(result.event_count, 2U);
        EXPECT_EQ(events[0].kind, EventKind::Rejected);
        EXPECT_EQ(events[0].reject_reason, test.reason);
        EXPECT_EQ(events[0].client, 7U);
        EXPECT_EQ(events[0].command_seq, ++sequence);
        EXPECT_EQ(events[1].kind, EventKind::CommandComplete);
        EXPECT_EQ(events[1].completion, CompletionStatus::Rejected);
        EXPECT_EQ(events[1].event_seq, 2 * sequence);
    }
    EXPECT_EQ(engine.snapshot(), BookSnapshot{});
}

TEST(Protocol, EveryFramePrefixReportsTheFullExpectedSize) {
    const std::array frames{
        encode(Welcome{1}), encode(Command{1, 2, LimitOrder{3, Side::Buy, 4, 5}}),
        encode(Command{1, 2, MarketOrder{3, Side::Buy, 5}}),
        encode(Command{1, 2, CancelOrder{3}}), encode(Event{}), encode(llmatch::Bbo{})};
    for (const auto& frame : frames) {
        for (std::size_t length = 0; length < frame.size; ++length) {
            SCOPED_TRACE(length);
            const auto info = inspect(frame.bytes().first(length));
            EXPECT_EQ(info.status, FrameStatus::NeedMore);
            EXPECT_EQ(info.frame_size, length < header_size ? header_size : frame.size);
            EXPECT_EQ(info.error, Error::None);
            expect_error([&] { (void)decode(frame.bytes().first(length)); }, Error::IncompleteFrame);
        }
        const auto full = inspect(frame.bytes());
        EXPECT_EQ(full.status, FrameStatus::Ready);
        EXPECT_EQ(full.frame_size, frame.size);
        EXPECT_EQ(full.error, Error::None);
    }
}

TEST(Protocol, FragmentedAndCoalescedFramesConsumeOnlyTheFirstFrame) {
    const std::array<Command, 3> expected{{
        {17, 11, LimitOrder{1, Side::Buy, 100, 3}},
        {17, 12, MarketOrder{2, Side::Sell, 1}}, {17, 13, CancelOrder{1}}
    }};
    std::vector<std::uint8_t> stream;
    for (const auto& command : expected) {
        const auto frame = encode(command);
        stream.insert(stream.end(), frame.bytes().begin(), frame.bytes().end());
    }
    EXPECT_EQ(inspect(stream).frame_size, 41U);
    for (std::size_t chunk = 1; chunk <= stream.size(); ++chunk) {
        std::vector<std::uint8_t> pending;
        std::vector<Command> received;
        for (std::size_t cursor = 0; cursor < stream.size();) {
            const auto count = std::min(chunk, stream.size() - cursor);
            pending.insert(pending.end(), stream.begin() + static_cast<std::ptrdiff_t>(cursor),
                           stream.begin() + static_cast<std::ptrdiff_t>(cursor + count));
            cursor += count;
            for (;;) {
                const auto info = inspect(pending);
                ASSERT_NE(info.status, FrameStatus::Invalid);
                if (info.status == FrameStatus::NeedMore) break;
                received.push_back(decode_request(std::span(pending).first(info.frame_size), 17));
                pending.erase(pending.begin(), pending.begin() + static_cast<std::ptrdiff_t>(info.frame_size));
            }
        }
        EXPECT_TRUE(pending.empty());
        EXPECT_EQ(received, std::vector(expected.begin(), expected.end()));
    }
}

TEST(Protocol, MalformedHeadersAreRejectedBeforeReadingAPayload) {
    struct Case { const char* bytes; Error error; };
    constexpr std::array cases{
        Case{"0002 0002 00000021", Error::UnsupportedVersion},
        Case{"0001 0000 00000000", Error::UnknownMessageType},
        Case{"0001 ffff 00000000", Error::UnknownMessageType},
        Case{"0001 0002 00000000", Error::InvalidPayloadLength},
        Case{"0001 0002 00000020", Error::InvalidPayloadLength},
        Case{"0001 0002 00000022", Error::InvalidPayloadLength},
        Case{"0001 0002 000000f8", Error::InvalidPayloadLength},
        Case{"0001 0002 000000f9", Error::FrameTooLarge},
        Case{"0001 0002 ffffffff", Error::FrameTooLarge}
    };
    for (const auto& test : cases) {
        const auto bytes = hex(test.bytes);
        const auto info = inspect(bytes);
        EXPECT_EQ(info.status, FrameStatus::Invalid);
        EXPECT_EQ(info.frame_size, 0U);
        EXPECT_EQ(info.error, test.error);
        expect_error([&] { (void)decode_request(bytes, 1); }, test.error);
    }
}

TEST(Protocol, ExactDecoderRejectsTrailingDataAndResponseOnRequestPath) {
    const auto welcome = encode(Welcome{1});
    expect_error([&] { (void)decode_request(welcome.bytes(), 1); }, Error::UnexpectedMessageType);
    const auto event = encode(Event{});
    expect_error([&] { (void)decode_request(event.bytes(), 1); }, Error::UnexpectedMessageType);
    const auto bbo = encode(llmatch::Bbo{});
    expect_error([&] { (void)decode_request(bbo.bytes(), 1); }, Error::UnexpectedMessageType);
    const auto cancel = encode(Command{1, 1, CancelOrder{2}});
    std::vector bytes(cancel.bytes().begin(), cancel.bytes().end());
    bytes.push_back(0);
    EXPECT_EQ(inspect(bytes).status, FrameStatus::Ready);
    expect_error([&] { (void)decode_request(bytes, 1); }, Error::TrailingBytes);
    bytes.insert(bytes.end(), cancel.bytes().begin(), cancel.bytes().end());
    expect_error([&] { (void)decode(bytes); }, Error::TrailingBytes);
}

TEST(Protocol, ResponseEnumAndBooleanSyntaxIsValidated) {
    // Payload offsets of the six enums, independently read from the schema.
    constexpr std::array<std::size_t, 6> offsets{0, 1, 38, 39, 40, 41};
    for (const auto offset : offsets) {
        auto frame = encode(Event{});
        frame.storage[header_size + offset] = 255;
        expect_error([&] { (void)decode(frame.bytes()); }, Error::InvalidField);
    }
    for (const std::size_t offset : {0U, 1U}) {
        auto frame = encode(llmatch::Bbo{});
        frame.storage[header_size + offset] = 2;
        expect_error([&] { (void)decode(frame.bytes()); }, Error::InvalidField);
    }
}

} // namespace
} // namespace llmatch::protocol
