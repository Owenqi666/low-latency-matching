#pragma once

#include "llmatch/event.hpp"
#include "llmatch/snapshot.hpp"

#include <filesystem>
#include <iosfwd>
#include <optional>
#include <span>
#include <string>
#include <vector>

namespace llmatch::validation {

enum class DifferenceKind { ProcessStatus, EventCount, EventValue, Snapshot, Invariant };
struct Difference {
    DifferenceKind kind;
    std::size_t command_index; // Zero-based position in the supplied trace.
    std::size_t event_index{};
    EventKind event_kind{};
    ProcessResult baseline_result{};
    ProcessResult reference_result{};
    std::vector<Event> baseline_events;
    std::vector<Event> reference_events;
    BookSnapshot baseline_snapshot;
    BookSnapshot reference_snapshot;
    std::string detail;
};

// Always starts both engines empty and compares every command's complete output.
std::optional<Difference> compare(EngineConfig config, std::span<const Command> commands);
bool same_failure_kind(const Difference& first, const Difference& second);
std::string difference_name(const Difference& difference);
void write_difference(std::ostream& output, const Difference& difference);
void save_failure(const std::filesystem::path& directory, EngineConfig config,
                  std::span<const Command> commands, const Difference& difference,
                  std::optional<std::uint64_t> seed = std::nullopt,
                  const std::string& generator_version = "external-trace");

}
