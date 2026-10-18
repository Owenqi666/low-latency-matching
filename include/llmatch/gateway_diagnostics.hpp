#pragma once

#include "llmatch/types.hpp"

#include <array>
#include <bit>
#include <cstddef>
#include <cstdint>

namespace llmatch {

// All of these records are Gateway-owned. They are inspected after run() or
// from that same thread, never from the Matching worker.
struct DurationHistogram {
    // Bucket 0 includes 0 and 1ns; bucket k covers [2^k, 2^(k+1)-1].
    std::array<std::uint64_t, 64> buckets{};
    std::uint64_t count{};
    std::uint64_t maximum_ns{};
    void observe(std::uint64_t ns) {
        const auto bucket = static_cast<std::size_t>(ns == 0 ? 0 : std::bit_width(ns) - 1);
        ++buckets[bucket];
        ++count;
        if (ns > maximum_ns) maximum_ns = ns;
    }
};

template<class T, std::size_t Capacity> struct BoundedDiagnosticRecords {
    std::array<T, Capacity> records{};
    std::size_t size{};
    std::uint64_t overflow{};
    void append(const T& value) {
        if (size < Capacity) records[size++] = value;
        else ++overflow;
    }
};

struct OutboundObservation {
    ClientId client{};
    std::size_t bytes{}, frames{}, in_flight_bytes{}, in_flight_frames{};
    std::size_t max_bytes{}, max_frames{}, max_in_flight_bytes{}, max_in_flight_frames{};
    std::uint64_t write_operations{}, write_callbacks{}, write_error_callbacks{};
    std::uint64_t last_write_started_ns{}, last_callback_ns{};
};

struct GatewayCloseObservation {
    std::uint64_t closed_ns{};
    std::size_t reason{};
    OutboundObservation outbound;
};

struct GatewayWindowObservation {
    std::uint64_t planned_ns{}, observed_ns{};
    std::size_t command_depth{}, event_depth{}, connections{};
    std::uint64_t admitted{}, events_consumed{}, bbo_consumed{};
    std::uint64_t write_operations{}, write_callbacks{}, bytes_transferred{};
    std::uint64_t write_operations_delta{}, write_callbacks_delta{}, bytes_transferred_delta{};
};

struct GatewayConnectionWindow {
    std::uint64_t observed_ns{};
    OutboundObservation outbound;
};

struct GatewayDiagnostics {
    static constexpr std::uint64_t sample_period_ns = 10'000'000;
    static constexpr std::size_t close_capacity = 128;
    static constexpr std::size_t window_capacity = 4096;
    static constexpr std::size_t connection_window_capacity = 16384;
    DurationHistogram whole_write_completion;
    DurationHistogram callback_interval;
    DurationHistogram loop_lateness;
    BoundedDiagnosticRecords<GatewayCloseObservation, close_capacity> closes;
    BoundedDiagnosticRecords<GatewayWindowObservation, window_capacity> windows;
    BoundedDiagnosticRecords<GatewayConnectionWindow, connection_window_capacity> connections;
    GatewayWindowObservation previous_window;
};

} // namespace llmatch
