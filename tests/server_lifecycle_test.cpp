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

} // namespace llmatch
