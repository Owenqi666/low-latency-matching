#include "llmatch/pipeline.hpp"

#include <algorithm>
#include <array>
#include <cassert>
#include <chrono>
#include <limits>
#include <stdexcept>

namespace llmatch {
namespace {
PipelineConfig checked_config(PipelineConfig config) {
    if (config.command_capacity == 0 || config.event_capacity == 0) {
        throw std::invalid_argument("queue capacities must be positive");
    }
    // Boost allocates capacity + 1 elements for its runtime SPSC ring.
    const auto max = std::numeric_limits<std::size_t>::max();
    if (config.command_capacity > max / sizeof(AdmissionRecord) - 1 ||
        config.event_capacity > max / sizeof(ServiceMessage) - 1) {
        throw std::invalid_argument("queue storage size is not representable");
    }
    return config;
}
bool same_quote(const Bbo& a, const Bbo& b) {
    return a.bid_present == b.bid_present && a.ask_present == b.ask_present &&
        a.bid_price == b.bid_price && a.bid_qty == b.bid_qty &&
        a.ask_price == b.ask_price && a.ask_qty == b.ask_qty;
}
}

std::uint64_t steady_now_ns() {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}

std::uint64_t event_checksum(std::uint64_t previous, const Event& event) {
    // Explicit wire fields avoid padding bytes and cover every business field.
    const auto frame = protocol::encode(event);
    for (const auto byte : frame.bytes()) {
        previous = (previous ^ byte) * 1099511628211ULL;
    }
    return previous;
}

MatchingPipeline::MatchingPipeline(PipelineConfig config, std::function<void()> notify_gateway)
    : config_(checked_config(config)), engine_(config.engine),
      commands_(config.command_capacity), events_(config.event_capacity),
      notify_gateway_(std::move(notify_gateway)) {
    admissions_.reserve(config_.record_limit);
    completions_.reserve(config_.record_limit);
    worker_ = std::thread([this] { run(); });
}

MatchingPipeline::~MatchingPipeline() {
    request_abort();
    join();
}

SubmitResult MatchingPipeline::try_submit(const Command& command, std::uint64_t frame_ready_ns) {
    std::lock_guard lock(wake_mutex_);
    if (drain_requested_ || abort_requested_ || done()) return SubmitResult::Stopping;
    if (config_.record_limit && admissions_.size() == config_.record_limit) {
        return SubmitResult::RecordLimit;
    }
    const auto now = steady_now_ns();
    const AdmissionRecord record{command, now, now - frame_ready_ns};
    if (!commands_.push(record)) return SubmitResult::Full;
    ++admitted_;
    command_high_water_ = std::max(command_high_water_, commands_.read_available());
    if (config_.record_limit) admissions_.push_back(record);
    wake_.notify_one();
    return SubmitResult::Admitted;
}

bool MatchingPipeline::try_pop(ServiceMessage& message) {
    // The same mutex as wait's predicate closes the check-to-sleep window.
    std::lock_guard lock(wake_mutex_);
    if (!events_.pop(message)) return false;
    wake_.notify_one();
    return true;
}

bool MatchingPipeline::has_output() const { return events_.read_available() != 0; }
bool MatchingPipeline::has_command_space() const { return commands_.write_available() != 0; }
std::size_t MatchingPipeline::command_depth() const {
    return config_.command_capacity - commands_.write_available();
}
std::size_t MatchingPipeline::event_depth() const { return events_.read_available(); }

void MatchingPipeline::request_drain() {
    std::lock_guard lock(wake_mutex_);
    drain_requested_ = true;
    wake_.notify_one();
}

void MatchingPipeline::request_abort() {
    std::lock_guard lock(wake_mutex_);
    abort_requested_ = true;
    wake_.notify_one();
}

void MatchingPipeline::join() { if (worker_.joinable()) worker_.join(); }

BookSnapshot MatchingPipeline::final_snapshot() const {
    assert(done() && !worker_.joinable());
    return engine_.snapshot();
}

void MatchingPipeline::run() {
    try {
        std::array<ServiceMessage, 2> pending;
        std::size_t pending_at = 0;
        std::size_t pending_count = 0;
        AdmissionRecord current{};
        CompletionRecord completion{};
        Bbo previous_quote{};
        bool active = false;
        for (;;) {
            bool started = false;
            {
                std::unique_lock lock(wake_mutex_);
                if (active && events_.write_available() == 0) {
                    ++stats_.output_waits;
                    stats_.phase = "waiting_output";
                }
                wake_.wait(lock, [&] {
                    if (abort_requested_) return true;
                    if (active) return events_.write_available() != 0;
                    return commands_.read_available() != 0 || drain_requested_;
                });
                if (abort_requested_) { aborted_ = true; break; }
                if (!active) {
                    if (!commands_.pop(current)) {
                        assert(drain_requested_);
                        break;
                    }
                    active = true;
                    stats_.current_admission = stats_.completed + 1;
                    started = true;
                    completion = {};
                    completion.admitted_ns = current.admitted_ns;
                    completion.checksum = checksum_basis;
                }
            }
            if (started) notify_gateway_(); // A command slot is now available.
            if (events_.write_available() == 0) continue;
            stats_.phase = "matching";
            if (!engine_.active() && pending_count == 0) {
                if (engine_.begin(current.command) != CallError::None) {
                    throw std::runtime_error("cannot begin admitted command: sequence exhausted or busy");
                }
            }
            if (pending_count == 0) {
                // One free queue slot exists; two fixed local slots can hold the
                // final BBO and Complete without reserving two queue slots.
                Event event;
                [[maybe_unused]] const bool produced = engine_.next(event);
                assert(produced);
                pending_at = 0;
                if (event.kind == EventKind::CommandComplete) {
                    const auto top = engine_.top_of_book();
                    Bbo quote{top.bid_present, top.ask_present, top.bid_price,
                              top.bid_qty, top.ask_price, top.ask_qty,
                              event.command_seq, event.event_seq - 1};
                    if (!same_quote(quote, previous_quote)) {
                        pending[pending_count++] = quote;
                        previous_quote = quote;
                    }
                }
                pending[pending_count++] = event;
            }
            const auto& message = pending[pending_at];
            const auto* event = std::get_if<Event>(&message);
            const bool is_complete = event && event->kind == EventKind::CommandComplete;
            stats_.phase = is_complete ? "publishing_complete" : event ? "publishing_event" : "publishing_bbo";
            [[maybe_unused]] const bool published = events_.push(message);
            assert(published); // Single producer; only the consumer can free slots.
            const auto published_ns = is_complete ? steady_now_ns() : 0;
            stats_.event_high_water = std::max(stats_.event_high_water,
                                               std::max(std::size_t{1}, events_.read_available()));
            bool finished = false;
            if (event) {
                ++stats_.events;
                stats_.last_event_seq = event->event_seq;
                ++completion.events;
                completion.trades += event->kind == EventKind::Trade;
                if (config_.record_limit) completion.checksum = event_checksum(completion.checksum, *event);
                if (event->kind == EventKind::CommandComplete) {
                    completion.command_seq = event->command_seq;
                    completion.completed_ns = published_ns;
                    completion.status = event->completion;
                    ++stats_.completed;
                    if (config_.record_limit) completions_.push_back(completion);
                    finished = true;
                }
            } else {
                ++stats_.bbo_updates;
            }
            ++pending_at;
            if (pending_at == pending_count) pending_at = pending_count = 0;
            if (finished) {
                assert(pending_count == 0);
                active = false;
                stats_.current_admission = 0;
                stats_.phase = "idle";
            }
            notify_gateway_();
        }
    } catch (const std::exception& error) {
        failure_ = error.what();
    }
    done_.store(true, std::memory_order_release);
    notify_gateway_();
}

} // namespace llmatch
