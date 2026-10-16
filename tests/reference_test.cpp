#include "reference_engine.hpp"
#include <gtest/gtest.h>
#include <vector>

namespace {
using namespace llmatch;

std::vector<Event> run(ReferenceEngine& engine, const Command& command) {
    std::vector<Event> events(engine.required_event_capacity());
    const auto result = engine.process(command, events);
    EXPECT_EQ(result.status, ProcessStatus::Processed);
    engine.check_invariants();
    events.resize(result.event_count);
    return events;
}

TEST(Reference, PriceThenArrivalSurvivesUnorderedErasure) {
    ReferenceEngine engine({8, 200, 100});
    run(engine, {1, 1, LimitOrder{101, Side::Sell, 100, 5}});
    run(engine, {2, 2, LimitOrder{102, Side::Sell, 100, 7}});
    run(engine, {3, 3, LimitOrder{103, Side::Sell, 99, 2}});
    run(engine, {4, 4, LimitOrder{104, Side::Sell, 100, 6}});
    run(engine, {1, 5, CancelOrder{101}});

    // Cancelling vector's first order moves #104 ahead of #102 physically.
    // The scan must still choose the best price, followed by the oldest order.
    const auto events = run(engine, {5, 6, MarketOrder{201, Side::Buy, 10}});
    ASSERT_EQ(events.size(), 5U);
    EXPECT_EQ(events[0].kind, EventKind::Accepted);
    for (std::size_t i = 1; i <= 3; ++i) EXPECT_EQ(events[i].kind, EventKind::Trade);
    EXPECT_EQ(events[1].maker_id, 103U);
    EXPECT_EQ(events[1].price, 99);
    EXPECT_EQ(events[1].qty, 2U);
    EXPECT_EQ(events[1].maker_arrival_seq, 3U);
    EXPECT_EQ(events[2].maker_id, 102U);
    EXPECT_EQ(events[2].qty, 7U);
    EXPECT_EQ(events[2].maker_arrival_seq, 2U);
    EXPECT_EQ(events[3].maker_id, 104U);
    EXPECT_EQ(events[3].qty, 1U);
    EXPECT_EQ(events[3].taker_arrival_seq, 6U);
    EXPECT_EQ(events.back().filled_qty, 10U);
    const BookSnapshot expected{{}, {{100, 5, {{104, 4, Side::Sell, 100, 5, 4}}}}};
    EXPECT_EQ(engine.snapshot(), expected);
}

TEST(Reference, SellLimitTakesHighestBidsThenRestsAtOwnLimit) {
    ReferenceEngine engine({8, 200, 100});
    run(engine, {1, 1, LimitOrder{11, Side::Buy, 99, 4}});
    run(engine, {2, 2, LimitOrder{12, Side::Buy, 101, 3}});
    run(engine, {3, 3, LimitOrder{13, Side::Buy, 101, 2}});
    run(engine, {4, 4, LimitOrder{14, Side::Buy, 97, 1}});
    const auto events = run(engine, {5, 5, LimitOrder{15, Side::Sell, 98, 12}});
    ASSERT_EQ(events.size(), 6U);
    EXPECT_EQ(events[1].maker_id, 12U);
    EXPECT_EQ(events[1].price, 101);
    EXPECT_EQ(events[2].maker_id, 13U);
    EXPECT_EQ(events[2].price, 101);
    EXPECT_EQ(events[3].maker_id, 11U);
    EXPECT_EQ(events[3].price, 99);
    EXPECT_EQ(events[4].kind, EventKind::Rested);
    EXPECT_EQ(events[4].price, 98);
    EXPECT_EQ(events[4].qty, 3U);
    EXPECT_EQ(events.back().filled_qty, 9U);
    EXPECT_EQ(events.back().resting_qty, 3U);
    const BookSnapshot expected{
        {{97, 1, {{14, 4, Side::Buy, 97, 1, 4}}}},
        {{98, 3, {{15, 5, Side::Sell, 98, 3, 5}}}}
    };
    EXPECT_EQ(engine.snapshot(), expected);
}

TEST(Reference, IocCancellationAndOwnerCheckedUserCancellation) {
    ReferenceEngine engine({8, 200, 100});
    auto events = run(engine, {1, 1, MarketOrder{1, Side::Buy, 6}});
    ASSERT_EQ(events.size(), 3U);
    EXPECT_EQ(events[1].kind, EventKind::Cancelled);
    EXPECT_EQ(events[1].qty, 6U);
    EXPECT_EQ(events[1].cancel_reason, CancelReason::IocRemainder);
    EXPECT_EQ(events.back().cancelled_qty, 6U);
    EXPECT_EQ(engine.snapshot(), BookSnapshot{});

    run(engine, {1, 2, LimitOrder{1, Side::Sell, 100, 7}});
    const auto before = engine.snapshot();
    events = run(engine, {2, 3, CancelOrder{1}});
    ASSERT_EQ(events.size(), 2U);
    EXPECT_EQ(events[0].reject_reason, RejectReason::NotOwner);
    EXPECT_EQ(events[1].completion, CompletionStatus::Rejected);
    EXPECT_EQ(engine.snapshot(), before);

    events = run(engine, {1, 4, CancelOrder{1}});
    ASSERT_EQ(events.size(), 3U);
    EXPECT_EQ(events[1].cancel_reason, CancelReason::UserCancel);
    EXPECT_EQ(events[1].qty, 7U);
    EXPECT_EQ(events[2].cancelled_qty, 7U);
    EXPECT_EQ(engine.snapshot(), BookSnapshot{});
    EXPECT_EQ(run(engine, {1, 5, CancelOrder{1}})[0].reject_reason, RejectReason::UnknownOrder);
}

TEST(Reference, FullBookRejectsCrossingLimitBeforeAnyTrade) {
    ReferenceEngine engine({1, 200, 100});
    run(engine, {1, 1, LimitOrder{1, Side::Sell, 100, 5}});
    const auto before = engine.snapshot();
    auto events = run(engine, {2, 2, LimitOrder{2, Side::Buy, 101, 5}});
    ASSERT_EQ(events.size(), 2U);
    EXPECT_EQ(events[0].reject_reason, RejectReason::CapacityExceeded);
    EXPECT_EQ(engine.snapshot(), before);
    EXPECT_EQ(run(engine, {2, 3, MarketOrder{1, Side::Buy, 5}})[0].reject_reason, RejectReason::DuplicateOrder);
    events = run(engine, {2, 4, MarketOrder{2, Side::Buy, 5}});
    ASSERT_EQ(events.size(), 3U);
    EXPECT_EQ(events[1].kind, EventKind::Trade);
    EXPECT_EQ(events[1].qty, 5U);
    EXPECT_EQ(engine.snapshot(), BookSnapshot{});
}

TEST(Reference, RepeatedInputsHaveIdenticalEventsAndCanonicalSnapshots) {
    ReferenceEngine first({8, 200, 100});
    ReferenceEngine second({8, 200, 100});
    const std::vector<Command> commands{
        {1, 1, LimitOrder{10, Side::Buy, 95, 7}},
        {1, 1, LimitOrder{11, Side::Buy, 97, 3}}, // RequestId is not deduplicated.
        {2, 1, LimitOrder{12, Side::Sell, 101, 8}},
        {2, 2, MarketOrder{13, Side::Sell, 4}},
        {1, 2, CancelOrder{10}},
        {1, 3, LimitOrder{10, Side::Buy, 102, 10}}, // A retired OrderId is reusable.
        {2, 3, CancelOrder{12}}
    };
    for (const auto& command : commands) {
        EXPECT_EQ(run(first, command), run(second, command));
        EXPECT_EQ(first.snapshot(), second.snapshot());
    }
    const BookSnapshot expected{{{102, 2, {{10, 1, Side::Buy, 102, 2, 6}}}}, {}};
    EXPECT_EQ(first.snapshot(), expected);
}

} // namespace
