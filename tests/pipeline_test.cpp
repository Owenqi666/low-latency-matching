#include "llmatch/pipeline.hpp"
#include "random_commands.hpp"
#include "reference_engine.hpp"

#include <gtest/gtest.h>

#include <array>
#include <chrono>
#include <condition_variable>
#include <limits>
#include <mutex>
#include <span>
#include <vector>

namespace llmatch {
namespace {
using Clock = std::chrono::steady_clock;
using namespace std::chrono_literals;

// The real notification callback also provides a deterministic pause immediately
// before the worker rechecks its wait predicate. No sleeps or worker-state reads.
class GatewaySignal {
public:
    void hold_notification(std::size_t number) {
        std::lock_guard lock(mutex_);
        hold_at_ = number;
    }
    void notify() {
        std::unique_lock lock(mutex_);
        ++generation_;
        if (generation_ == hold_at_) held_ = true;
        cv_.notify_all();
        if (held_ && !released_) {
            if (!cv_.wait_until(lock, Clock::now() + 5s, [&] { return released_; })) {
                timed_out_ = true;
                released_ = true;
            }
        }
    }
    bool wait_held() {
        std::unique_lock lock(mutex_);
        return cv_.wait_until(lock, Clock::now() + 5s, [&] { return held_; });
    }
    void release() {
        std::lock_guard lock(mutex_);
        released_ = true;
        cv_.notify_all();
    }
    std::size_t generation() {
        std::lock_guard lock(mutex_);
        return generation_;
    }
    bool wait_change(std::size_t previous, Clock::time_point deadline) {
        std::unique_lock lock(mutex_);
        return cv_.wait_until(lock, deadline, [&] { return generation_ != previous; });
    }
    bool timed_out() {
        std::lock_guard lock(mutex_);
        return timed_out_;
    }
private:
    std::mutex mutex_;
    std::condition_variable cv_;
    std::size_t generation_{};
    std::size_t hold_at_{std::numeric_limits<std::size_t>::max()};
    bool held_{};
    bool released_{};
    bool timed_out_{};
};

bool drain(MatchingPipeline& pipeline, GatewaySignal& signal, std::vector<ServiceMessage>& output) {
    const auto deadline = Clock::now() + 5s;
    while (!pipeline.done() || pipeline.has_output()) {
        const auto previous = signal.generation();
        ServiceMessage message;
        bool progress = false;
        while (pipeline.try_pop(message)) {
            output.push_back(message);
            progress = true;
        }
        if (pipeline.done() && !pipeline.has_output()) break;
        if (Clock::now() >= deadline ||
            (!progress && !signal.wait_change(previous, deadline))) {
            pipeline.request_abort();
            pipeline.join();
            return false;
        }
    }
    pipeline.join();
    return true;
}

bool run_commands(MatchingPipeline& pipeline, GatewaySignal& signal,
                  std::span<const Command> commands, std::vector<ServiceMessage>& output) {
    const auto deadline = Clock::now() + 10s;
    std::size_t submitted = 0;
    while (submitted < commands.size()) {
        const auto previous = signal.generation();
        bool progress = false;
        const auto result = pipeline.try_submit(commands[submitted], steady_now_ns());
        if (result == SubmitResult::Admitted) {
            ++submitted;
            progress = true;
        } else if (result != SubmitResult::Full) {
            pipeline.request_abort();
            pipeline.join();
            return false;
        }
        ServiceMessage message;
        while (pipeline.try_pop(message)) {
            output.push_back(message);
            progress = true;
        }
        if (Clock::now() >= deadline ||
            (!progress && !signal.wait_change(previous, deadline))) {
            pipeline.request_abort();
            pipeline.join();
            return false;
        }
    }
    pipeline.request_drain();
    return drain(pipeline, signal, output);
}

void compare_reference(const MatchingPipeline& pipeline, EngineConfig config,
                       std::span<const Command> commands, const std::vector<ServiceMessage>& actual) {
    ReferenceEngine reference(config);
    std::vector<Event> buffer(reference.required_event_capacity());
    std::vector<ServiceMessage> expected;
    TopOfBook previous{};
    std::size_t bbo_count = 0, business_count = 0;
    ASSERT_EQ(pipeline.admissions().size(), commands.size());
    ASSERT_EQ(pipeline.completions().size(), commands.size());
    for (std::size_t index = 0; index < commands.size(); ++index) {
        SCOPED_TRACE(index);
        const auto result = reference.process(commands[index], buffer);
        ASSERT_EQ(result.status, ProcessStatus::Processed);
        const auto events = std::span{buffer}.first(result.event_count);
        const auto& complete = events.back();
        ASSERT_EQ(complete.kind, EventKind::CommandComplete);
        for (const auto& event : events.first(events.size() - 1)) expected.emplace_back(event);
        const auto snapshot = reference.snapshot();
        TopOfBook quote{};
        if (!snapshot.bids.empty()) {
            quote.bid_present = true;
            quote.bid_price = snapshot.bids.front().price;
            quote.bid_qty = snapshot.bids.front().total_qty;
        }
        if (!snapshot.asks.empty()) {
            quote.ask_present = true;
            quote.ask_price = snapshot.asks.front().price;
            quote.ask_qty = snapshot.asks.front().total_qty;
        }
        if (quote != previous) {
            expected.emplace_back(Bbo{quote.bid_present, quote.ask_present,
                quote.bid_price, quote.bid_qty, quote.ask_price, quote.ask_qty,
                complete.command_seq, complete.event_seq - 1});
            previous = quote;
            ++bbo_count;
        }
        expected.emplace_back(complete);
        business_count += events.size();

        const auto& admission = pipeline.admissions()[index];
        EXPECT_EQ(admission.command, commands[index]);
        const auto& record = pipeline.completions()[index];
        EXPECT_EQ(record.command_seq, complete.command_seq);
        EXPECT_EQ(record.admitted_ns, admission.admitted_ns);
        EXPECT_GE(record.completed_ns, record.admitted_ns);
        EXPECT_EQ(record.events, events.size());
        EXPECT_EQ(record.status, complete.completion);
        std::uint64_t checksum = checksum_basis, trades = 0;
        for (const auto& event : events) {
            checksum = event_checksum(checksum, event);
            trades += event.kind == EventKind::Trade;
        }
        EXPECT_EQ(record.trades, trades);
        EXPECT_EQ(record.checksum, checksum);
    }
    EXPECT_EQ(actual, expected);
    EXPECT_EQ(pipeline.final_snapshot(), reference.snapshot());
    EXPECT_EQ(pipeline.admitted(), commands.size());
    EXPECT_EQ(pipeline.stats().completed, commands.size());
    EXPECT_EQ(pipeline.stats().events, business_count);
    EXPECT_EQ(pipeline.stats().bbo_updates, bbo_count);
    EXPECT_EQ(pipeline.stats().last_event_seq, business_count);
    EXPECT_FALSE(pipeline.aborted());
    EXPECT_TRUE(pipeline.failure().empty()) << pipeline.failure();
}

TEST(PipelineTest, TinyEventQueuesSweep64MakersWithOrderedBboAndComplete) {
    for (const std::size_t event_capacity : {1U, 2U, 4U}) {
        SCOPED_TRACE(event_capacity);
        const PipelineConfig config{{128, 1000, 1000}, 2, event_capacity, 100};
        std::vector<Command> commands;
        for (OrderId id = 1; id <= 64; ++id) {
            commands.push_back({1, id, LimitOrder{id, Side::Sell, 100 + static_cast<Price>(id / 2), 1}});
        }
        commands.push_back({2, 1, MarketOrder{100, Side::Buy, 70}});
        commands.push_back({2, 1, LimitOrder{100, Side::Buy, 90, 7}});
        commands.push_back({3, 1, MarketOrder{101, Side::Sell, 2}});
        commands.push_back({2, 1, CancelOrder{100}});
        GatewaySignal signal;
        MatchingPipeline pipeline(config, [&] { signal.notify(); });
        std::vector<ServiceMessage> output;
        ASSERT_TRUE(run_commands(pipeline, signal, commands, output));
        compare_reference(pipeline, config.engine, commands, output);
        EXPECT_LE(pipeline.stats().event_high_water, event_capacity);
        EXPECT_LE(pipeline.command_high_water(), config.command_capacity);
        const auto& sweep = pipeline.completions()[64];
        EXPECT_EQ(sweep.trades, 64U);
        EXPECT_EQ(sweep.events, 67U);
    }
}

TEST(PipelineTest, FullInputAndOutputDrainAfterNotificationBeforeWait) {
    const PipelineConfig config{{8, 1000, 1000}, 1, 1, 2};
    const std::array<Command, 2> commands{{
        {1, 1, LimitOrder{1, Side::Sell, 100, 5}},
        {2, 1, MarketOrder{2, Side::Buy, 5}}
    }};
    GatewaySignal signal;
    signal.hold_notification(2); // Pop notification, then first Accepted is queued.
    MatchingPipeline pipeline(config, [&] { signal.notify(); });
    ASSERT_EQ(pipeline.try_submit(commands[0], steady_now_ns()), SubmitResult::Admitted);
    ASSERT_TRUE(signal.wait_held());
    EXPECT_TRUE(pipeline.has_output());
    ASSERT_EQ(pipeline.try_submit(commands[1], steady_now_ns()), SubmitResult::Admitted);
    EXPECT_FALSE(pipeline.has_command_space());
    // RecordLimit has its own test; this case exercises the drain boundary.
    pipeline.request_drain();
    EXPECT_EQ(pipeline.try_submit(commands[0], steady_now_ns()), SubmitResult::Stopping);

    std::vector<ServiceMessage> output;
    ServiceMessage message;
    ASSERT_TRUE(pipeline.try_pop(message)); // Notify occurs before worker waits.
    output.push_back(message);
    EXPECT_EQ(std::get<Event>(message).kind, EventKind::Accepted);
    signal.release();
    ASSERT_TRUE(drain(pipeline, signal, output));
    EXPECT_FALSE(signal.timed_out());
    compare_reference(pipeline, config.engine, commands, output);
    EXPECT_EQ(pipeline.command_high_water(), 1U);
    EXPECT_EQ(pipeline.stats().event_high_water, 1U);
}

TEST(PipelineTest, FullInputReturnsFullAndRecoveryDoesNotReorderCommands) {
    const PipelineConfig config{{8, 1000, 1000}, 1, 1, 3};
    const std::array<Command, 2> commands{{
        {1, 1, LimitOrder{1, Side::Buy, 100, 2}},
        {1, 1, CancelOrder{1}}
    }};
    GatewaySignal signal;
    signal.hold_notification(2);
    MatchingPipeline pipeline(config, [&] { signal.notify(); });
    ASSERT_EQ(pipeline.try_submit(commands[0], steady_now_ns()), SubmitResult::Admitted);
    ASSERT_TRUE(signal.wait_held());
    ASSERT_EQ(pipeline.try_submit(commands[1], steady_now_ns()), SubmitResult::Admitted);
    EXPECT_EQ(pipeline.try_submit(commands[0], steady_now_ns()), SubmitResult::Full);
    EXPECT_EQ(pipeline.admitted(), 2U);
    EXPECT_FALSE(pipeline.has_command_space());
    pipeline.request_drain();
    signal.release();
    std::vector<ServiceMessage> output;
    ASSERT_TRUE(drain(pipeline, signal, output));
    compare_reference(pipeline, config.engine, commands, output);
    EXPECT_FALSE(signal.timed_out());
}

TEST(PipelineTest, AbortWakesOutputBlockedWorkerWithoutCompletingUnpublishedCommand) {
    const PipelineConfig config{{8, 1000, 1000}, 1, 1, 2};
    GatewaySignal signal;
    signal.hold_notification(2);
    MatchingPipeline pipeline(config, [&] { signal.notify(); });
    ASSERT_EQ(pipeline.try_submit({1, 1, LimitOrder{1, Side::Buy, 100, 5}}, steady_now_ns()),
              SubmitResult::Admitted);
    ASSERT_TRUE(signal.wait_held());
    ASSERT_EQ(pipeline.try_submit({1, 2, CancelOrder{1}}, steady_now_ns()), SubmitResult::Admitted);
    EXPECT_TRUE(pipeline.has_output());
    EXPECT_FALSE(pipeline.has_command_space());
    pipeline.request_abort();
    signal.release();
    const auto deadline = Clock::now() + 5s;
    while (!pipeline.done()) {
        const auto previous = signal.generation();
        if (pipeline.done()) break;
        ASSERT_TRUE(signal.wait_change(previous, deadline));
    }
    pipeline.join();
    EXPECT_TRUE(pipeline.aborted());
    EXPECT_TRUE(pipeline.failure().empty());
    EXPECT_EQ(pipeline.admitted(), 2U);
    EXPECT_EQ(pipeline.stats().completed, 0U);
    EXPECT_EQ(pipeline.stats().current_admission, 1U);
    // After the callback barrier is released the still-full queue selects the
    // output-wait phase before the abort predicate is observed.
    EXPECT_STREQ(pipeline.stats().phase, "waiting_output");
    EXPECT_EQ(pipeline.stats().events, 1U);
    EXPECT_EQ(pipeline.stats().last_event_seq, 1U);
    EXPECT_TRUE(pipeline.completions().empty());
    EXPECT_EQ(pipeline.final_snapshot(), BookSnapshot{});
    ServiceMessage message;
    ASSERT_TRUE(pipeline.try_pop(message));
    EXPECT_EQ(std::get<Event>(message).kind, EventKind::Accepted);
    EXPECT_FALSE(pipeline.try_pop(message));
    EXPECT_FALSE(signal.timed_out());
}

TEST(PipelineTest, EmptyDrainAndIdleAbortWakeWorker) {
    for (const bool abort : {false, true}) {
        GatewaySignal signal;
        MatchingPipeline pipeline({{1, 1000, 1000}, 1, 1, 0}, [&] { signal.notify(); });
        if (abort) pipeline.request_abort();
        else pipeline.request_drain();
        std::vector<ServiceMessage> output;
        ASSERT_TRUE(drain(pipeline, signal, output));
        EXPECT_TRUE(output.empty());
        EXPECT_EQ(pipeline.aborted(), abort);
        EXPECT_TRUE(pipeline.failure().empty());
        EXPECT_EQ(pipeline.stats().completed, 0U);
        EXPECT_EQ(pipeline.final_snapshot(), BookSnapshot{});
    }
}

TEST(PipelineTest, FixedSeedsCompareConcurrentOutputAndCompletionDigests) {
    for (const std::size_t event_capacity : {1U, 2U, 4U}) {
        const PipelineConfig config{{16, 1000, 1000}, 2, event_capacity, 2000};
        const auto commands = testing::random_commands(config.engine, 0x4D325000ULL + event_capacity, 2000);
        GatewaySignal signal;
        MatchingPipeline pipeline(config, [&] { signal.notify(); });
        std::vector<ServiceMessage> output;
        ASSERT_TRUE(run_commands(pipeline, signal, commands, output));
        compare_reference(pipeline, config.engine, commands, output);
        EXPECT_LE(pipeline.stats().event_high_water, event_capacity);
        EXPECT_LE(pipeline.command_high_water(), config.command_capacity);
    }
}

TEST(PipelineTest, ExperimentRecordLimitRejectsAdmissionWithoutHidingEarlierWork) {
    const PipelineConfig config{{2, 1000, 1000}, 1, 1, 1};
    const Command command{1, 1, MarketOrder{1, Side::Buy, 1}};
    GatewaySignal signal;
    MatchingPipeline pipeline(config, [&] { signal.notify(); });
    ASSERT_EQ(pipeline.try_submit(command, steady_now_ns()), SubmitResult::Admitted);
    EXPECT_EQ(pipeline.try_submit(command, steady_now_ns()), SubmitResult::RecordLimit);
    pipeline.request_drain();
    std::vector<ServiceMessage> output;
    ASSERT_TRUE(drain(pipeline, signal, output));
    compare_reference(pipeline, config.engine, std::span{&command, 1}, output);
}

TEST(PipelineTest, QueueCapacitiesRejectZeroAndUnrepresentableStorageBeforeAllocation) {
    for (const auto capacity : {std::size_t{0}, std::numeric_limits<std::size_t>::max()}) {
        EXPECT_THROW((MatchingPipeline({{1, 1000, 1000}, capacity, 1, 0}, [] {})), std::invalid_argument);
        EXPECT_THROW((MatchingPipeline({{1, 1000, 1000}, 1, capacity, 0}, [] {})), std::invalid_argument);
    }
}

} // namespace
} // namespace llmatch
