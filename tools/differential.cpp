#include "differential.hpp"

#include "llmatch/matching_engine.hpp"
#include "reference_engine.hpp"
#include "trace_io.hpp"

#include <algorithm>
#include <fstream>
#include <stdexcept>

namespace llmatch::validation {

std::optional<Difference> compare(EngineConfig config, std::span<const Command> commands) {
    MatchingEngine baseline(config);
    ReferenceEngine reference(config);
    std::vector<Event> actual(baseline.required_event_capacity());
    std::vector<Event> expected(reference.required_event_capacity());
    for (std::size_t index = 0; index < commands.size(); ++index) {
        const auto a = baseline.process(commands[index], actual);
        const auto b = reference.process(commands[index], expected);
        const auto a_events = std::span(actual).first(a.event_count);
        const auto b_events = std::span(expected).first(b.event_count);
        auto a_snapshot = baseline.snapshot();
        auto b_snapshot = reference.snapshot();
        std::optional<DifferenceKind> kind;
        std::size_t event_index = 0;
        EventKind event_kind{};
        std::string detail;
        if (a.status != b.status) {
            kind = DifferenceKind::ProcessStatus;
        } else if (a.event_count != b.event_count) {
            kind = DifferenceKind::EventCount;
        } else {
            for (; event_index < a.event_count; ++event_index) {
                if (actual[event_index] != expected[event_index]) {
                    kind = DifferenceKind::EventValue;
                    event_kind = expected[event_index].kind;
                    break;
                }
            }
        }
        if (!kind && a_snapshot != b_snapshot) kind = DifferenceKind::Snapshot;
        if (!kind) {
            try {
                baseline.check_invariants();
            } catch (const std::logic_error& error) {
                kind = DifferenceKind::Invariant;
                detail = std::string("baseline: ") + error.what();
            }
            try {
                reference.check_invariants();
            } catch (const std::logic_error& error) {
                kind = DifferenceKind::Invariant;
                detail += std::string(" reference: ") + error.what();
            }
        }
        if (kind) {
            return Difference{*kind, index, event_index, event_kind, a, b,
                              {a_events.begin(), a_events.end()},
                              {b_events.begin(), b_events.end()},
                              std::move(a_snapshot), std::move(b_snapshot), std::move(detail)};
        }
        if (a.status != ProcessStatus::Processed) {
            throw std::runtime_error("trace execution stopped with a call-level error at command " +
                                     std::to_string(index + 1));
        }
    }
    return std::nullopt;
}

bool same_failure_kind(const Difference& first, const Difference& second) {
    return first.kind == second.kind &&
           (first.kind != DifferenceKind::EventValue || first.event_kind == second.event_kind) &&
           (first.kind != DifferenceKind::Invariant || first.detail == second.detail);
}

std::string difference_name(const Difference& difference) {
    switch (difference.kind) {
        case DifferenceKind::ProcessStatus: return "process_status";
        case DifferenceKind::EventCount: return "event_count";
        case DifferenceKind::EventValue:
            return "event_value_kind_" + std::to_string(static_cast<unsigned>(difference.event_kind));
        case DifferenceKind::Snapshot: return "snapshot";
        case DifferenceKind::Invariant: return "invariant";
    }
    throw std::logic_error("unknown difference kind");
}

void write_difference(std::ostream& output, const Difference& difference) {
    output << "difference " << difference_name(difference)
           << "\ncommand_index_zero_based " << difference.command_index
           << "\ncommand_number " << difference.command_index + 1
           << "\nevent_index_zero_based " << difference.event_index
           << "\ndetail " << difference.detail
           << "\nbaseline_status " << static_cast<unsigned>(difference.baseline_result.status)
           << "\nbaseline_event_count " << difference.baseline_result.event_count
           << "\nreference_status " << static_cast<unsigned>(difference.reference_result.status)
           << "\nreference_event_count " << difference.reference_result.event_count
           << "\nbaseline_events\n";
    trace::write_events(output, difference.baseline_events);
    output << "reference_events\n";
    trace::write_events(output, difference.reference_events);
    output << "baseline_snapshot\n";
    trace::write_snapshot(output, difference.baseline_snapshot);
    output << "reference_snapshot\n";
    trace::write_snapshot(output, difference.reference_snapshot);
}

void save_failure(const std::filesystem::path& directory, EngineConfig config,
                  std::span<const Command> commands, const Difference& difference,
                  std::optional<std::uint64_t> seed, const std::string& generator_version) {
    std::filesystem::create_directories(directory);
    trace::write_config(directory / "config.txt", config);
    trace::write_trace(directory / "input.trace", commands);
    std::ofstream report(directory / "difference.txt");
    report.exceptions(std::ios::failbit | std::ios::badbit);
    write_difference(report, difference);
    report.close();
    std::ofstream metadata(directory / "metadata.txt");
    metadata.exceptions(std::ios::failbit | std::ios::badbit);
    metadata << "generator_version " << generator_version << "\nseed ";
    if (seed) metadata << *seed;
    else metadata << "unknown";
    metadata << "\ncommand_count " << commands.size()
             << "\ninput_hash " << trace::file_hash(directory / "input.trace")
             << "\nconfig_hash " << trace::file_hash(directory / "config.txt") << '\n';
    metadata.close();
}

}
