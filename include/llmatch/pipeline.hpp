#pragma once

#include "llmatch/matching_engine.hpp"
#include "llmatch/protocol.hpp"

#include <boost/lockfree/spsc_queue.hpp>
#include <atomic>
#include <condition_variable>
#include <functional>
#include <mutex>
#include <string>
#include <thread>
#include <variant>
#include <vector>

namespace llmatch {

using ServiceMessage = std::variant<Event, Bbo>;

struct PipelineConfig {
    EngineConfig engine{1000, 20000, 1000000};
    std::size_t command_capacity{1024};
    std::size_t event_capacity{1024};
    // Zero disables per-command experiment records. Counters remain enabled.
    std::size_t record_limit{};
};

struct AdmissionRecord {
    Command command;
    std::uint64_t admitted_ns{};
    std::uint64_t gateway_wait_ns{};
};

struct CompletionRecord {
    Sequence command_seq{};
    std::uint64_t admitted_ns{};
    std::uint64_t completed_ns{};
    std::uint64_t events{};
    std::uint64_t trades{};
    std::uint64_t checksum{};
    CompletionStatus status{};
};

struct PipelineStats {
    std::uint64_t completed{};
    std::uint64_t events{};
    std::uint64_t bbo_updates{};
    std::uint64_t last_event_seq{};
    std::size_t event_high_water{};
    std::uint64_t output_waits{};
    // One-based admitted-trace position; zero when no command is in progress.
    std::uint64_t current_admission{};
    const char* phase{"idle"};
};

enum class SubmitResult { Admitted, Full, Stopping, RecordLimit };

std::uint64_t steady_now_ns();
std::uint64_t event_checksum(std::uint64_t previous, const Event& event);
inline constexpr std::uint64_t checksum_basis = 14695981039346656037ULL;

// Gateway alone calls submit/pop/drain. The worker alone touches the engine.
// Experiment records and the final snapshot are inspected only after join().
class MatchingPipeline {
public:
    MatchingPipeline(PipelineConfig config, std::function<void()> notify_gateway);
    ~MatchingPipeline();
    MatchingPipeline(const MatchingPipeline&) = delete;
    MatchingPipeline& operator=(const MatchingPipeline&) = delete;

    SubmitResult try_submit(const Command& command, std::uint64_t frame_ready_ns);
    bool try_pop(ServiceMessage& message);
    bool has_output() const;
    bool has_command_space() const;
    // Gateway-side snapshots of queue occupancy; may change immediately after
    // observation. These do not read Matching-owned PipelineStats.
    std::size_t command_depth() const;
    std::size_t event_depth() const;
    void request_drain();
    void request_abort();
    bool done() const noexcept { return done_.load(std::memory_order_acquire); }
    void join();

    std::uint64_t admitted() const noexcept { return admitted_; }
    std::size_t command_high_water() const noexcept { return command_high_water_; }
    const std::vector<AdmissionRecord>& admissions() const { return admissions_; }
    const std::vector<CompletionRecord>& completions() const { return completions_; }
    const PipelineStats& stats() const { return stats_; }
    const std::string& failure() const { return failure_; }
    bool aborted() const noexcept { return aborted_; }
    BookSnapshot final_snapshot() const;

private:
    void run();
    PipelineConfig config_;
    MatchingEngine engine_;
    boost::lockfree::spsc_queue<AdmissionRecord> commands_;
    boost::lockfree::spsc_queue<ServiceMessage> events_;
    std::function<void()> notify_gateway_;
    std::mutex wake_mutex_;
    std::condition_variable wake_;
    bool drain_requested_{};
    bool abort_requested_{};
    std::atomic<bool> done_{};
    std::thread worker_;

    // Gateway-owned until join.
    std::uint64_t admitted_{};
    std::size_t command_high_water_{};
    std::vector<AdmissionRecord> admissions_;
    // Worker-owned until join.
    PipelineStats stats_;
    std::vector<CompletionRecord> completions_;
    std::string failure_;
    bool aborted_{};
};

} // namespace llmatch
