#pragma once

#include "llmatch/command.hpp"

#include <filesystem>
#include <map>
#include <string>
#include <vector>

namespace llmatch::testing {

// Separate from mt19937_64-modulo-v1: existing workloads retain their seed meaning.
inline constexpr const char* deep_book_generator_version = "deep-book-mt19937_64-v1";
enum class DeepBookDistribution { LongFifo, SparseWide };
enum class DeepBookPhase { Prefill, Tail, CapacityBoundary };

struct DeepBookSample {
    std::size_t command_number;
    DeepBookPhase phase;
    std::size_t live_orders;
    std::size_t price_levels;
    std::size_t max_fifo_depth;
    Price minimum_price;
    Price maximum_price;
    bool operator==(const DeepBookSample&) const = default;
};

struct DeepBookTrace {
    std::vector<Command> commands;
    std::vector<DeepBookSample> samples;
    // Counts are derived from actual reference events and before/after snapshots.
    std::map<std::string, std::size_t> operations;
    bool operator==(const DeepBookTrace&) const = default;
};

const char* deep_book_distribution_name(DeepBookDistribution distribution);
const char* deep_book_phase_name(DeepBookPhase phase);

// Prefills floor(0.85*C), emits exactly tail_commands ordinary tail commands
// (including replenishment), then exercises full capacity and restores floor(0.85*C).
// The boundary phase is reported separately and every command remains in the trace.
DeepBookTrace deep_book_commands(EngineConfig config, std::uint64_t seed,
                                 DeepBookDistribution distribution, std::size_t tail_commands);
void save_deep_book(const std::filesystem::path& directory, EngineConfig config,
                   std::uint64_t seed, DeepBookDistribution distribution,
                   const DeepBookTrace& generated);

} // namespace llmatch::testing
