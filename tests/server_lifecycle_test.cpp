#include "llmatch/server.hpp"

#include <gtest/gtest.h>
#include <stdexcept>

namespace llmatch {

struct ServerTestAccess {
    static void enter_draining_pump(MatchingServer& server) {
        server.draining_ = true;
        server.pump_scheduled_.store(true, std::memory_order_release);
    }
    static void maybe_finish(MatchingServer& server) { server.maybe_finish(); }
    static void rearm_pump(MatchingServer& server) { server.rearm_pump(); }
    static bool finished(const MatchingServer& server) { return server.finished_; }
    static bool pump_scheduled(const MatchingServer& server) {
        return server.pump_scheduled_.load(std::memory_order_acquire);
    }
    static void drain_and_join(MatchingServer& server) {
        server.pipeline_->request_drain();
        server.pipeline_->join();
    }
    static void post_consumer_failure(MatchingServer& server) {
        boost::asio::post(server.io_, [] { throw std::runtime_error("injected Gateway consumer failure"); });
    }
    static void sample(MatchingServer& server, std::uint64_t planned, std::uint64_t actual) {
        server.sample_diagnostics(planned, actual);
    }
    static bool await_timer_sample(MatchingServer& server) {
        server.schedule_diagnostic_sample();
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
        while (!server.diagnostics_->windows.size && std::chrono::steady_clock::now() < deadline) {
            server.io_.run_one_for(std::chrono::milliseconds(100));
        }
        return server.diagnostics_->windows.size != 0;
    }
    static void finish_and_flush(MatchingServer& server) {
        drain_and_join(server);
        server.finish(false);
        server.io_.run();
    }
};

TEST(ServerLifecycle, CoalescedWorkerDoneFinishesAtPumpRearm) {
    ServerConfig config;
    config.port = 0;
    MatchingServer server(config);

    // Model the pump's final check while the empty worker is still waiting.
    // The io_context is never run, so no timer or later callback can finish us.
    ServerTestAccess::enter_draining_pump(server);
    ASSERT_FALSE(server.pipeline().done());
    ServerTestAccess::maybe_finish(server);
    ASSERT_FALSE(ServerTestAccess::finished(server));

    // Complete the real worker in the check-to-clear window. Its notification
    // observes the set flag and is coalesced with this already-running pump.
    ServerTestAccess::drain_and_join(server);
    ASSERT_TRUE(server.pipeline().done());
    ASSERT_FALSE(server.pipeline().has_output());
    ASSERT_TRUE(ServerTestAccess::pump_scheduled(server));
    ASSERT_FALSE(ServerTestAccess::finished(server));

    ServerTestAccess::rearm_pump(server);
    EXPECT_TRUE(ServerTestAccess::finished(server));
    EXPECT_FALSE(ServerTestAccess::pump_scheduled(server));
    EXPECT_TRUE(server.failure().empty());
    EXPECT_FALSE(server.pipeline().aborted());
}

TEST(ServerLifecycle, GatewayCallbackExceptionAbortsAndJoinsWorker) {
    ServerConfig config;
    config.port = 0;
    MatchingServer server(config);
    ServerTestAccess::post_consumer_failure(server);

    EXPECT_EQ(server.run(), 1);
    EXPECT_EQ(server.failure(), "injected Gateway consumer failure");
    EXPECT_TRUE(server.pipeline().done());
    EXPECT_TRUE(server.pipeline().aborted());
    EXPECT_EQ(server.pipeline().admitted(), 0U);
    EXPECT_EQ(server.pipeline().stats().completed, 0U);
    EXPECT_EQ(server.pipeline().stats().current_admission, 0U);
    EXPECT_STREQ(server.pipeline().stats().phase, "idle");
    // final_snapshot requires a joined worker, not merely a notified stop flag.
    EXPECT_EQ(server.pipeline().final_snapshot(), BookSnapshot{});
}

TEST(ServerLifecycle, DiagnosticsDisabledDoesNotAllocateOrCollect) {
    ServerConfig config;
    config.port = 0;
    MatchingServer server(config);
    EXPECT_EQ(server.diagnostics(), nullptr);
    ServerTestAccess::sample(server, 100, 200);
    EXPECT_EQ(server.diagnostics(), nullptr);
}

TEST(ServerLifecycle, DiagnosticWindowsStayBoundedAndContinueAfterOverflow) {
    ServerConfig config;
    config.port = 0;
    config.gateway_diagnostics = true;
    MatchingServer server(config);
    ASSERT_NE(server.diagnostics(), nullptr);
    for (std::uint64_t i = 0; i < GatewayDiagnostics::window_capacity + 3; ++i) {
        ServerTestAccess::sample(server, 100 + i * 100, 150 + i * 100);
    }
    const auto& diagnostics = *server.diagnostics();
    EXPECT_EQ(diagnostics.windows.size, GatewayDiagnostics::window_capacity);
    EXPECT_EQ(diagnostics.windows.overflow, 3U);
    EXPECT_EQ(diagnostics.loop_lateness.count, GatewayDiagnostics::window_capacity + 3);
    EXPECT_EQ(diagnostics.loop_lateness.maximum_ns, 50U);
    EXPECT_EQ(diagnostics.windows.records[0].observed_ns, 150U);
    EXPECT_EQ(diagnostics.previous_window.observed_ns, 150 + (GatewayDiagnostics::window_capacity + 2) * 100);
    EXPECT_EQ(diagnostics.previous_window.command_depth, 0U);
    EXPECT_EQ(diagnostics.previous_window.event_depth, 0U);
    ServerTestAccess::drain_and_join(server);
    EXPECT_TRUE(server.pipeline().done());
    EXPECT_TRUE(server.pipeline().failure().empty());
}

TEST(GatewayDiagnostics, HistogramsAndRecordOverflowHaveExplicitBounds) {
    DurationHistogram histogram;
    for (const auto value : {0ULL, 1ULL, 2ULL, 3ULL, 4ULL, ~0ULL}) histogram.observe(value);
    EXPECT_EQ(histogram.count, 6U);
    EXPECT_EQ(histogram.buckets[0], 2U);
    EXPECT_EQ(histogram.buckets[1], 2U);
    EXPECT_EQ(histogram.buckets[2], 1U);
    EXPECT_EQ(histogram.buckets[63], 1U);
    BoundedDiagnosticRecords<GatewayCloseObservation, 2> closes;
    for (std::uint64_t i = 1; i <= 5; ++i) closes.append({i, 0, {}});
    EXPECT_EQ(closes.size, 2U);
    EXPECT_EQ(closes.overflow, 3U);
    EXPECT_EQ(closes.records[0].closed_ns, 1U);
    EXPECT_EQ(closes.records[1].closed_ns, 2U);
}

TEST(ServerLifecycle, RealDiagnosticTimerCollectsAndCancelsOnFinish) {
    ServerConfig config;
    config.port = 0;
    config.gateway_diagnostics = true;
    MatchingServer server(config);
    ASSERT_TRUE(ServerTestAccess::await_timer_sample(server));
    const auto before = server.diagnostics()->windows.size;
    ASSERT_GE(before, 1U);
    const auto& sample = server.diagnostics()->windows.records[0];
    EXPECT_GT(sample.planned_ns, 0U);
    EXPECT_GE(sample.observed_ns, sample.planned_ns);
    ServerTestAccess::finish_and_flush(server);
    EXPECT_EQ(server.diagnostics()->windows.size, before);
    EXPECT_TRUE(ServerTestAccess::finished(server));
}

} // namespace llmatch
