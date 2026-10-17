#pragma once

#include "llmatch/pipeline.hpp"
#include <boost/asio.hpp>
#include <array>
#include <map>
#include <memory>
#include <optional>

namespace llmatch {

struct ServerConfig {
    PipelineConfig pipeline;
    std::string address{"127.0.0.1"};
    std::uint16_t port{19999};
    std::size_t max_connections{64};
    std::size_t send_limit{64 * 1024};
    std::chrono::milliseconds shutdown_timeout{5000};
    // Zero uses the OS default. A small value makes slow-peer tests reproducible.
    int socket_send_buffer{};
};

enum class CloseReason : std::size_t {
    PeerEof, ReadError, WriteError, Protocol, TruncatedFrame, SlowClient, Shutdown, Count
};
const char* close_reason_name(CloseReason reason);

struct ServerStats {
    std::uint64_t connections{};
    std::uint64_t connection_limit_rejections{};
    std::uint64_t consumed_events{};
    std::uint64_t consumed_bbo{};
    std::uint64_t missing_business_recipients{};
    std::uint64_t written_business_frames{};
    std::uint64_t written_frames{};
    std::uint64_t discarded_business_frames{};
    std::uint64_t discarded_frames{};
    std::size_t send_high_water{};
    // Application async_write operations, not socket system calls. These
    // counters cover the entire server lifetime, including setup traffic.
    std::size_t write_batch_max_frames{};
    std::size_t write_batch_max_bytes{};
    std::uint64_t write_operations{};
    std::uint64_t write_callbacks{};
    std::uint64_t write_error_callbacks{};
    std::uint64_t write_frames_submitted{};
    std::uint64_t write_bytes_submitted{};
    std::uint64_t write_bytes_transferred{};
    std::array<std::uint64_t, 17> write_batch_frames{}; // Index is frame count; 0 is unused.
    std::array<std::uint64_t, 16> write_batch_bytes{};  // Upper bounds 256, 512, ..., 4096.
    // Error callbacks and callbacks observed after close remain unconfirmed,
    // even when their local transfer count contains complete frame prefixes.
    std::uint64_t unconfirmed_write_callbacks{};
    std::uint64_t unconfirmed_write_bytes{};
    std::uint64_t unconfirmed_write_complete_frames{};
    std::array<std::uint64_t, static_cast<std::size_t>(CloseReason::Count)> closes{};
};

class MatchingServer {
public:
    explicit MatchingServer(ServerConfig config);
    ~MatchingServer();
    // Run on the Gateway/main thread. Signal handling requests graceful drain.
    int run();
    std::uint16_t port() const;
    const ServerConfig& config() const { return config_; }
    const ServerStats& stats() const { return stats_; }
    const MatchingPipeline& pipeline() const { return *pipeline_; }
    const std::string& failure() const { return failure_; }

private:
    friend struct ServerTestAccess;
    struct Connection;
    using Tcp = boost::asio::ip::tcp;
    void accept_next();
    void schedule_pump();
    void pump();
    void rearm_pump();
    void route(const ServiceMessage& message);
    void send_to(ClientId client, const protocol::Frame& frame);
    void begin_shutdown(const std::string& failure = {});
    void maybe_finish();
    void finish(bool timed_out);
    bool runnable_input() const;

    ServerConfig config_;
    boost::asio::io_context io_;
    boost::asio::executor_work_guard<boost::asio::io_context::executor_type> work_;
    Tcp::acceptor acceptor_;
    boost::asio::signal_set signals_;
    boost::asio::steady_timer shutdown_timer_;
    std::unique_ptr<MatchingPipeline> pipeline_;
    std::map<ClientId, std::shared_ptr<Connection>> connections_;
    std::vector<ClientId> pump_clients_;
    std::size_t round_robin_{};
    ClientId next_client_{1};
    Bbo cached_bbo_{};
    ServerStats stats_;
    std::atomic<bool> pump_scheduled_{};
    bool draining_{};
    bool finished_{};
    std::string failure_;
};

} // namespace llmatch
