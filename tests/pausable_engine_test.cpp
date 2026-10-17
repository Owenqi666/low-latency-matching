#include "llmatch/matching_engine.hpp"
#include "random_commands.hpp"
#include "reference_engine.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <utility>
#include <vector>

namespace llmatch {

struct PausableEngineTestAccess {
    static void sequences(MatchingEngine& engine, Sequence command, Sequence event) {
        engine.command_seq_ = command;
        engine.event_seq_ = event;
    }
    static auto sequences(const MatchingEngine& engine) {
        return std::pair{engine.command_seq_, engine.event_seq_};
    }
};

namespace {
constexpr EngineConfig config{128, 1000, 1000};

template<class Engine>
std::vector<Event> synchronous(Engine& engine, const Command& command) {
    std::vector<Event> output(engine.required_event_capacity());
    const auto result = engine.process(command, output);
    EXPECT_EQ(result.status, ProcessStatus::Processed);
    output.resize(result.event_count);
    return output;
}

void expect_busy_unchanged(MatchingEngine& engine) {
    const auto book = engine.snapshot();
    const auto sequences = PausableEngineTestAccess::sequences(engine);
    EXPECT_EQ(engine.begin({99, 99, MarketOrder{999, Side::Buy, 1000}}), CallError::Busy);
    EXPECT_EQ(engine.snapshot(), book);
    EXPECT_EQ(PausableEngineTestAccess::sequences(engine), sequences);
}

void compare_paused(MatchingEngine& engine, ReferenceEngine& reference, const Command& command) {
    const auto expected = synchronous(reference, command);
    const auto before = engine.snapshot();
    ASSERT_EQ(engine.begin(command), CallError::None);
    EXPECT_EQ(engine.snapshot(), before);
    for (const auto& event : expected) {
        ASSERT_TRUE(engine.active());
        expect_busy_unchanged(engine);
        Event actual{};
        ASSERT_TRUE(engine.next(actual));
        EXPECT_EQ(actual, event);
        engine.check_invariants();
    }
    EXPECT_FALSE(engine.active());
    EXPECT_EQ(engine.snapshot(), reference.snapshot());
    Event sentinel;
    std::memset(&sentinel, 0xA5, sizeof(sentinel));
    const auto bytes = std::as_bytes(std::span{&sentinel, 1});
    const std::vector<std::byte> saved(bytes.begin(), bytes.end());
    EXPECT_FALSE(engine.next(sentinel));
    EXPECT_EQ(std::memcmp(&sentinel, saved.data(), sizeof(sentinel)), 0);
}

TEST(PausableEngineTest, AdmissionAndEveryTradeAdvanceOnlyWhenNextIsCalled) {
    MatchingEngine engine(config);
    ReferenceEngine reference(config);
    const std::array<Command, 2> setup{{
        {1, 1, LimitOrder{10, Side::Sell, 100, 10}},
        {2, 2, LimitOrder{20, Side::Sell, 101, 10}}
    }};
    for (const auto& command : setup) {
        EXPECT_EQ(synchronous(engine, command), synchronous(reference, command));
    }
    Command command{3, 3, MarketOrder{30, Side::Buy, 12}};
    const auto expected = synchronous(reference, command);
    const auto before = engine.snapshot();
    ASSERT_EQ(engine.begin(command), CallError::None);
    command = {99, 99, CancelOrder{20}}; // begin owns a value, not caller storage.
    EXPECT_EQ(engine.snapshot(), before);
    expect_busy_unchanged(engine);

    Event event{};
    ASSERT_TRUE(engine.next(event));
    EXPECT_EQ(event, expected[0]);
    EXPECT_EQ(engine.snapshot(), before); // Accepted alone never fills an order.
    expect_busy_unchanged(engine);

    ASSERT_TRUE(engine.next(event));
    EXPECT_EQ(event, expected[1]);
    const auto after_first = engine.snapshot();
    ASSERT_EQ(after_first.asks.size(), 1U);
    EXPECT_EQ(after_first.asks[0].price, 101);
    EXPECT_EQ(after_first.asks[0].total_qty, 10U);
    expect_busy_unchanged(engine);

    ASSERT_TRUE(engine.next(event));
    EXPECT_EQ(event, expected[2]);
    EXPECT_EQ(engine.snapshot().asks[0].total_qty, 8U);
    expect_busy_unchanged(engine);
    ASSERT_TRUE(engine.next(event));
    EXPECT_EQ(event, expected[3]);
    EXPECT_FALSE(engine.active());
    EXPECT_EQ(engine.snapshot(), reference.snapshot());
}

TEST(PausableEngineTest, OneTwoAndFourOutputSlotsSweep64MakersWithoutLosingRemainder) {
    for (const std::size_t slots : {1U, 2U, 4U}) {
        for (const Side side : {Side::Buy, Side::Sell}) {
            for (const bool limit : {false, true}) {
                SCOPED_TRACE(::testing::Message() << "slots=" << slots << " side="
                    << static_cast<int>(side) << " limit=" << limit);
                MatchingEngine engine(config);
                ReferenceEngine reference(config);
                for (OrderId id = 1; id <= 64; ++id) {
                    const Side maker_side = side == Side::Buy ? Side::Sell : Side::Buy;
                    const Price price = side == Side::Buy
                        ? 100 + static_cast<Price>(id / 2) : 400 - static_cast<Price>(id / 2);
                    const Command maker{1, id, LimitOrder{id, maker_side, price, 1}};
                    EXPECT_EQ(synchronous(engine, maker), synchronous(reference, maker));
                }
                Command command{2, 65, MarketOrder{100, side, 70}};
                if (limit) command.payload = LimitOrder{100, side, side == Side::Buy ? 500 : 50, 70};
                const auto expected = synchronous(reference, command);
                ASSERT_EQ(std::count_if(expected.begin(), expected.end(), [](const Event& event) {
                    return event.kind == EventKind::Trade;
                }), 64);
                ASSERT_EQ(engine.begin(command), CallError::None);
                std::array<Event, 4> queue{};
                std::size_t head = 0, count = 0, consumed = 0;
                while (engine.active() || count != 0) {
                    while (engine.active() && count < slots) {
                        ASSERT_TRUE(engine.next(queue[(head + count) % slots]));
                        ++count;
                        engine.check_invariants();
                    }
                    // A full output window stops all calls to next. A later begin
                    // cannot use that pause to bypass the outstanding command.
                    if (engine.active()) expect_busy_unchanged(engine);
                    ASSERT_GT(count, 0U);
                    ASSERT_LT(consumed, expected.size());
                    EXPECT_EQ(queue[head], expected[consumed++]);
                    head = (head + 1) % slots;
                    --count;
                }
                EXPECT_EQ(consumed, expected.size());
                EXPECT_EQ(engine.snapshot(), reference.snapshot());
                EXPECT_EQ(expected.back().filled_qty, 64U);
                EXPECT_EQ(expected.back().resting_qty, limit ? 6U : 0U);
                EXPECT_EQ(expected.back().cancelled_qty, limit ? 0U : 6U);
            }
        }
    }
}

TEST(PausableEngineTest, FixedSeedsCompareEveryPausedEventAndFinalSnapshot) {
    for (const std::size_t capacity : {1U, 2U, 16U, 128U}) {
        const EngineConfig small{capacity, 1000, 1000};
        MatchingEngine engine(small);
        ReferenceEngine reference(small);
        const auto commands = testing::random_commands(small, 0x4D320000ULL + capacity, 2000);
        for (std::size_t index = 0; index < commands.size(); ++index) {
            SCOPED_TRACE(::testing::Message() << "capacity=" << capacity << " command=" << index);
            compare_paused(engine, reference, commands[index]);
        }
    }
}

TEST(PausableEngineTest, RejectedCancelAndRestingStagesResumeWithoutRepeatingEffects) {
    const EngineConfig small{1, 1000, 1000};
    MatchingEngine engine(small);
    ReferenceEngine reference(small);
    const std::array<Command, 7> commands{{
        {1, 1, LimitOrder{10, Side::Sell, 100, 5}},
        {2, 2, LimitOrder{20, Side::Buy, 100, 5}}, // Full capacity rejects before any trade.
        {2, 2, CancelOrder{10}}, // Ownership rejection.
        {1, 1, CancelOrder{10}}, // Repeated request ID still executes.
        {1, 1, LimitOrder{10, Side::Buy, 90, 3}}, // Reuse both request and inactive order ID.
        {1, 1, MarketOrder{20, Side::Sell, 3}},
        {1, 1, CancelOrder{10}}
    }};
    for (const auto& command : commands) compare_paused(engine, reference, command);
}

TEST(PausableEngineTest, SynchronousMisuseAndSmallOutputCannotDisturbPausedCommand) {
    MatchingEngine engine(config);
    const Command command{1, 1, LimitOrder{10, Side::Buy, 100, 5}};
    ASSERT_EQ(engine.begin(command), CallError::None);
    Event accepted{};
    ASSERT_TRUE(engine.next(accepted));
    const auto before = engine.snapshot();
    const auto sequences = PausableEngineTestAccess::sequences(engine);
    std::vector<Event> output(engine.required_event_capacity());
    std::memset(output.data(), 0xA5, output.size() * sizeof(Event));
    const auto bytes = std::as_bytes(std::span{output});
    const std::vector<std::byte> saved(bytes.begin(), bytes.end());
    EXPECT_EQ(engine.process(command, std::span{output}.first(1)).status,
              ProcessStatus::OutputBufferTooSmall);
    EXPECT_THROW(engine.process(command, output), std::logic_error);
    EXPECT_EQ(engine.snapshot(), before);
    EXPECT_EQ(PausableEngineTestAccess::sequences(engine), sequences);
    EXPECT_EQ(std::memcmp(output.data(), saved.data(), saved.size()), 0);
    ASSERT_TRUE(engine.next(output[0]));
    EXPECT_EQ(output[0].kind, EventKind::Rested);
    ASSERT_TRUE(engine.next(output[1]));
    EXPECT_EQ(output[1].kind, EventKind::CommandComplete);
    EXPECT_EQ(output[1].resting_qty, 5U);
}

TEST(PausableEngineTest, SequenceExhaustionDoesNotBeginOrWriteAnEvent) {
    const auto max = std::numeric_limits<Sequence>::max();
    for (const bool command_exhausted : {false, true}) {
        MatchingEngine engine(config);
        const Command resting{1, 1, LimitOrder{10, Side::Buy, 100, 5}};
        synchronous(engine, resting);
        PausableEngineTestAccess::sequences(engine, command_exhausted ? max : 1,
            command_exhausted ? 3 : max - engine.required_event_capacity() + 1);
        const auto before = engine.snapshot();
        const auto sequences = PausableEngineTestAccess::sequences(engine);
        EXPECT_EQ(engine.begin({1, 2, CancelOrder{10}}), CallError::SequenceExhausted);
        EXPECT_FALSE(engine.active());
        EXPECT_EQ(engine.snapshot(), before);
        EXPECT_EQ(PausableEngineTestAccess::sequences(engine), sequences);
        Event output;
        std::memset(&output, 0xA5, sizeof(output));
        std::array<std::byte, sizeof(Event)> saved{};
        std::memcpy(saved.data(), &output, sizeof(output));
        EXPECT_FALSE(engine.next(output));
        EXPECT_EQ(std::memcmp(&output, saved.data(), saved.size()), 0);
    }
}

TEST(PausableEngineTest, LastRepresentableCommandResumesAfterBusyWithoutWrapping) {
    MatchingEngine engine(config);
    const auto max = std::numeric_limits<Sequence>::max();
    const auto first_event = max - engine.required_event_capacity() + 1;
    PausableEngineTestAccess::sequences(engine, max - 1, first_event - 1);
    ASSERT_EQ(engine.begin({1, 1, MarketOrder{10, Side::Buy, 5}}), CallError::None);
    for (Sequence index = 0; index < 3; ++index) {
        expect_busy_unchanged(engine); // Busy takes precedence over exhausted CommandSeq.
        Event event{};
        ASSERT_TRUE(engine.next(event));
        EXPECT_EQ(event.command_seq, max);
        EXPECT_EQ(event.event_seq, first_event + index);
    }
    EXPECT_FALSE(engine.active());
    EXPECT_EQ(engine.begin({1, 2, CancelOrder{10}}), CallError::SequenceExhausted);
}

TEST(PausableEngineTest, TopOfBookCopiesBestPriceAndLevelAggregateWithZeroEmptySides) {
    MatchingEngine engine(config);
    EXPECT_EQ(engine.top_of_book(), TopOfBook{});
    synchronous(engine, {1, 1, LimitOrder{1, Side::Buy, 90, 3}});
    synchronous(engine, {1, 2, LimitOrder{2, Side::Buy, 90, 4}});
    synchronous(engine, {1, 3, LimitOrder{3, Side::Sell, 100, 8}});
    const TopOfBook both{true, true, 90, 7, 100, 8};
    EXPECT_EQ(engine.top_of_book(), both);
    synchronous(engine, {1, 4, LimitOrder{4, Side::Buy, 80, 2}});
    EXPECT_EQ(engine.top_of_book(), both); // Deep levels do not change the BBO.
    synchronous(engine, {2, 5, MarketOrder{5, Side::Sell, 5}});
    EXPECT_EQ(engine.top_of_book(), (TopOfBook{true, true, 90, 2, 100, 8}));
    synchronous(engine, {1, 6, CancelOrder{2}});
    EXPECT_EQ(engine.top_of_book(), (TopOfBook{true, true, 80, 2, 100, 8}));
    synchronous(engine, {1, 7, CancelOrder{4}});
    EXPECT_EQ(engine.top_of_book(), (TopOfBook{false, true, 0, 0, 100, 8}));
    synchronous(engine, {1, 8, CancelOrder{3}});
    EXPECT_EQ(engine.top_of_book(), TopOfBook{});
    EXPECT_EQ(both, (TopOfBook{true, true, 90, 7, 100, 8}));
}

} // namespace
} // namespace llmatch
