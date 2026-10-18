#include "send_queue.hpp"

#include <gtest/gtest.h>
#include <functional>
#include <numeric>
#include <type_traits>
#include <utility>
#include <vector>

namespace llmatch {
namespace {
namespace asio = boost::asio;
using boost::system::error_code;

// Only a controlled AsyncWriteStream. The actual asio::async_write composition
// consumes short writes, and SendQueue supplies production selection/accounting.
// Payload bytes are read at step(), not copied when the write is initiated.
class ManualWriteStream {
public:
    using executor_type = asio::io_context::executor_type;
    explicit ManualWriteStream(asio::io_context& io) : io_(io) {}
    executor_type get_executor() noexcept { return io_.get_executor(); }

    template<class Buffers, class Handler>
    void async_write_some(const Buffers& buffers, Handler&& handler) {
        EXPECT_FALSE(pending_);
        buffers_.assign(asio::buffer_sequence_begin(buffers), asio::buffer_sequence_end(buffers));
        auto completion = std::make_shared<std::decay_t<Handler>>(std::forward<Handler>(handler));
        pending_ = [completion](error_code error, std::size_t count) mutable {
            (*completion)(error, count);
        };
        ++write_some_calls;
    }

    bool pending() const { return bool(pending_); }
    std::size_t remaining() const { return asio::buffer_size(buffers_); }

    void step(std::size_t count, error_code error = {}) {
        ASSERT_TRUE(pending_);
        ASSERT_LE(count, remaining());
        auto left = count;
        for (const auto& buffer : buffers_) {
            const auto take = std::min(left, buffer.size());
            const auto* begin = static_cast<const std::uint8_t*>(buffer.data());
            bytes.insert(bytes.end(), begin, begin + take);
            left -= take;
            if (!left) break;
        }
        auto completion = std::move(pending_);
        pending_ = {};
        asio::post(io_, [completion = std::move(completion), error, count]() mutable {
            completion(error, count);
        });
        io_.restart();
        io_.poll();
    }

    std::vector<std::uint8_t> bytes;
    std::size_t write_some_calls{};

private:
    asio::io_context& io_;
    std::vector<asio::const_buffer> buffers_;
    std::function<void(error_code, std::size_t)> pending_;
};

protocol::Frame event_frame(std::uint64_t sequence) {
    Event event{};
    event.kind = EventKind::CommandComplete;
    event.command_seq = sequence;
    event.event_seq = sequence;
    event.client = 1;
    event.request = sequence;
    event.order_id = sequence;
    event.completion = CompletionStatus::Accepted;
    return protocol::encode(event);
}

void append_bytes(std::vector<std::uint8_t>& bytes, const protocol::Frame& frame) {
    bytes.insert(bytes.end(), frame.bytes().begin(), frame.bytes().end());
}

class SendQueueTest : public testing::Test {
protected:
    void TearDown() override {
        EXPECT_EQ(diagnostics->whole_write_completion.count, stats.write_callbacks);
        EXPECT_EQ(queue.observation().write_callbacks, stats.write_callbacks);
        EXPECT_EQ(queue.observation().write_operations, stats.write_operations);
        EXPECT_EQ(queue.observation().write_error_callbacks, stats.write_error_callbacks);
        EXPECT_GE(queue.observation().max_bytes, queue.bytes());
        EXPECT_GE(queue.observation().max_frames, queue.size());
    }
    void start() {
        asio::async_write(stream, queue.begin_write(), [this](error_code error, std::size_t count) {
            ++callbacks;
            last_error = error;
            transferred = count;
            queue.complete(error, count);
            if (error && !queue.closed()) queue.close();
        });
    }

    asio::io_context io;
    ServerStats stats;
    std::unique_ptr<GatewayDiagnostics> diagnostics = std::make_unique<GatewayDiagnostics>();
    detail::SendQueue queue{stats, 65536, diagnostics.get(), 17};
    ManualWriteStream stream{io};
    std::size_t callbacks{};
    std::size_t transferred{};
    error_code last_error;
};

TEST_F(SendQueueTest, SingleFrameDoesNotWaitForAnotherFrame) {
    const auto frame = event_frame(1);
    ASSERT_TRUE(queue.enqueue(frame, true));
    start();
    ASSERT_TRUE(stream.pending());
    EXPECT_EQ(stream.remaining(), frame.size);
    stream.step(frame.size);
    EXPECT_EQ(callbacks, 1U);
    EXPECT_TRUE(queue.empty());
    EXPECT_FALSE(queue.writing());
    EXPECT_EQ(stats.written_frames, 1U);
    EXPECT_EQ(stats.written_business_frames, 1U);
    EXPECT_EQ(stats.write_operations, 1U);
    EXPECT_EQ(stats.write_batch_frames[1], 1U);
    EXPECT_EQ(stats.write_bytes_transferred, frame.size);
}

TEST_F(SendQueueTest, MixedFrameBytesStayOrderedAcrossBatchBoundariesAndAppend) {
    std::vector<std::uint8_t> expected;
    std::size_t business = 0;
    // Put a BBO and Complete on opposite sides of the configured batch edge.
    for (std::size_t i = 0; i + 1 < detail::batch_max_frames; ++i) {
        const auto frame = event_frame(i + 1);
        ASSERT_TRUE(queue.enqueue(frame, true));
        append_bytes(expected, frame);
        ++business;
    }
    const auto bbo = protocol::encode(Bbo{});
    ASSERT_TRUE(queue.enqueue(bbo, false));
    append_bytes(expected, bbo);
    start();
    const auto first_batch_bytes = stream.remaining();
    // Force several deque allocations while the first operation retains its
    // descriptors. Appended frames cannot join an already-started operation.
    for (std::size_t i = 0; i < 80; ++i) {
        const auto frame = i % 3 == 2 ? protocol::encode(protocol::Welcome{7}) : event_frame(i + 100);
        const bool is_business = i % 3 != 2;
        ASSERT_TRUE(queue.enqueue(frame, is_business));
        append_bytes(expected, frame);
        business += is_business;
    }
    EXPECT_EQ(stream.remaining(), first_batch_bytes);
    while (!queue.empty()) {
        ASSERT_TRUE(stream.pending());
        const auto bytes = stream.remaining();
        ASSERT_LE(bytes, detail::batch_max_bytes);
        stream.step(1); // Exercise an actual composed short write every batch.
        EXPECT_TRUE(queue.writing());
        stream.step(bytes - 1);
        if (!queue.empty()) start();
    }
    EXPECT_EQ(stream.bytes, expected);
    EXPECT_EQ(stats.written_frames, detail::batch_max_frames + 80);
    EXPECT_EQ(stats.written_business_frames, business);
    EXPECT_EQ(stats.write_frames_submitted, stats.written_frames);
    EXPECT_EQ(stats.write_bytes_submitted, expected.size());
    EXPECT_EQ(stats.write_bytes_transferred, expected.size());
    EXPECT_EQ(stats.write_callbacks, stats.write_operations);
    EXPECT_EQ(stats.write_error_callbacks, 0U);
    EXPECT_EQ(stats.unconfirmed_write_callbacks, 0U);
    EXPECT_EQ(stats.discarded_frames, 0U);
    EXPECT_EQ(std::accumulate(stats.write_batch_frames.begin(), stats.write_batch_frames.end(), 0ULL), stats.write_operations);
    EXPECT_EQ(std::accumulate(stats.write_batch_bytes.begin(), stats.write_batch_bytes.end(), 0ULL), stats.write_operations);
    EXPECT_EQ(stream.write_some_calls, 2 * stats.write_operations);
}

TEST_F(SendQueueTest, ShortWriteThenCancellationPreservesBuffersAndCountsDiscardOnce) {
    const auto frame = event_frame(1);
    for (std::size_t i = 0; i < detail::batch_max_frames + 1; ++i) ASSERT_TRUE(queue.enqueue(frame, true));
    start();
    // Baseline: inside its one frame. Candidate: one whole frame plus a
    // prefix of the second. The same composed-operation test covers both.
    const auto prefix_frames = detail::batch_max_frames > 1 ? 1U : 0U;
    const auto partial = prefix_frames * frame.size + 7;
    stream.step(partial);
    EXPECT_EQ(callbacks, 0U);
    EXPECT_EQ(queue.bytes(), (detail::batch_max_frames + 1) * frame.size);
    const auto observed = queue.observation();
    EXPECT_EQ(observed.client, 17U);
    EXPECT_EQ(observed.in_flight_frames, detail::batch_max_frames);
    EXPECT_EQ(observed.in_flight_bytes, detail::batch_max_frames * frame.size);
    EXPECT_EQ(observed.write_callbacks, 0U); // Partial socket write is not a composed callback.
    queue.close();
    queue.close();
    EXPECT_TRUE(queue.writing());
    EXPECT_EQ(queue.size(), detail::batch_max_frames + 1);
    EXPECT_EQ(stats.discarded_frames, detail::batch_max_frames + 1);
    stream.step(0, asio::error::operation_aborted);
    EXPECT_EQ(callbacks, 1U);
    EXPECT_EQ(transferred, partial);
    EXPECT_EQ(last_error, asio::error::operation_aborted);
    EXPECT_TRUE(queue.empty());
    EXPECT_EQ(queue.bytes(), 0U);
    EXPECT_FALSE(queue.writing());
    EXPECT_EQ(stats.written_frames, 0U);
    EXPECT_EQ(stats.discarded_business_frames, detail::batch_max_frames + 1);
    EXPECT_EQ(stats.unconfirmed_write_callbacks, 1U);
    EXPECT_EQ(stats.unconfirmed_write_bytes, partial);
    EXPECT_EQ(stats.unconfirmed_write_complete_frames, prefix_frames);
    EXPECT_EQ(stats.write_error_callbacks, 1U);
    EXPECT_EQ(queue.observation().in_flight_bytes, 0U);
    EXPECT_EQ(queue.observation().in_flight_frames, 0U);
}

TEST_F(SendQueueTest, ErrorCallbackReportsFullPrefixWithoutConfirmingTheBatch) {
    const auto frame = event_frame(1);
    for (std::size_t i = 0; i < detail::batch_max_frames + 1; ++i) ASSERT_TRUE(queue.enqueue(frame, true));
    start();
    stream.step(frame.size, asio::error::connection_reset);
    EXPECT_EQ(callbacks, 1U);
    EXPECT_TRUE(queue.closed());
    EXPECT_TRUE(queue.empty());
    EXPECT_EQ(stats.written_frames, 0U);
    EXPECT_EQ(stats.discarded_frames, detail::batch_max_frames + 1);
    EXPECT_EQ(stats.unconfirmed_write_bytes, frame.size);
    EXPECT_EQ(stats.unconfirmed_write_complete_frames, 1U);
    queue.close();
    EXPECT_EQ(stats.discarded_frames, detail::batch_max_frames + 1);
}

TEST_F(SendQueueTest, CloseBeforeSuccessfulCallbackNeverReconfirmsDiscardedFrames) {
    const auto frame = event_frame(1);
    for (std::size_t i = 0; i < detail::batch_max_frames; ++i) ASSERT_TRUE(queue.enqueue(frame, true));
    start();
    const auto bytes = stream.remaining();
    queue.close();
    // The socket result can already be queued when another callback closes the
    // connection. Late success still carries unconfirmed diagnostic bytes.
    stream.step(bytes);
    EXPECT_FALSE(last_error);
    EXPECT_TRUE(queue.empty());
    EXPECT_EQ(stats.written_frames, 0U);
    EXPECT_EQ(stats.discarded_frames, detail::batch_max_frames);
    EXPECT_EQ(stats.unconfirmed_write_complete_frames, detail::batch_max_frames);
    EXPECT_EQ(stats.unconfirmed_write_bytes, bytes);
    EXPECT_EQ(stats.write_error_callbacks, 0U);
}

TEST_F(SendQueueTest, CancellationBeforeAnyBytesConfirmsNothing) {
    ASSERT_TRUE(queue.enqueue(event_frame(1), true));
    start();
    queue.close();
    stream.step(0, asio::error::operation_aborted);
    EXPECT_EQ(stats.write_callbacks, 1U);
    EXPECT_EQ(stats.unconfirmed_write_callbacks, 1U);
    EXPECT_EQ(stats.unconfirmed_write_bytes, 0U);
    EXPECT_EQ(stats.unconfirmed_write_complete_frames, 0U);
    EXPECT_EQ(stats.written_frames, 0U);
    EXPECT_EQ(stats.discarded_frames, 1U);
}

TEST(SendQueue, SendLimitIncludesInFlightBytesAndOverflowingFrame) {
    ServerStats stats;
    const auto frame = event_frame(1);
    detail::SendQueue queue(stats, frame.size * 2);
    ASSERT_TRUE(queue.enqueue(frame, true));
    const auto buffers = queue.begin_write();
    ASSERT_TRUE(queue.enqueue(frame, true));
    EXPECT_EQ(queue.bytes(), frame.size * 2);
    EXPECT_FALSE(queue.enqueue(frame, true));
    queue.close();
    EXPECT_EQ(stats.discarded_frames, 3U);
    EXPECT_EQ(stats.discarded_business_frames, 3U);
    EXPECT_EQ(stats.send_high_water, frame.size * 2);
    EXPECT_EQ(asio::buffer_size(buffers), frame.size);
    queue.complete(asio::error::operation_aborted, 0);
    EXPECT_TRUE(queue.empty());
    EXPECT_EQ(queue.bytes(), 0U);
    EXPECT_EQ(stats.discarded_frames, 3U);
}

} // namespace
} // namespace llmatch
