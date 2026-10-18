#include "deep_book_commands.hpp"
#include "differential.hpp"
#include "reference_engine.hpp"
#include "trace_io.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <set>
#include <span>
#include <string>
#include <utility>

namespace llmatch {
namespace {
using testing::DeepBookDistribution;
using testing::DeepBookPhase;

std::filesystem::path evidence_root() {
    if (const char* directory = std::getenv("LLMATCH_DEEP_BOOK_OUTPUT")) return directory;
    return "deep-book";
}

void run_case(std::size_t capacity, std::uint64_t seed, DeepBookDistribution distribution, std::size_t tail_count) {
    const EngineConfig config{capacity, 1000000000, 1000000};
    const auto directory = evidence_root() / (std::string(testing::deep_book_distribution_name(distribution)) +
        "-C" + std::to_string(capacity) + "-seed" + std::to_string(seed));
    SCOPED_TRACE(directory.string());
    const auto generated = testing::deep_book_commands(config, seed, distribution, tail_count);
    testing::save_deep_book(directory, config, seed, distribution, generated);
    // Read the actual serialized input, not an in-memory shortcut. Both engines
    // start empty, so the prefill is checked just as thoroughly as every tail step.
    const auto commands = trace::read_trace(directory / "input.trace");
    ASSERT_EQ(commands, generated.commands);
    ASSERT_EQ(trace::read_config(directory / "config.txt"), config);
    if (const auto difference = validation::compare(config, commands)) {
        validation::save_failure(directory / "failure", config,
            std::span(commands).first(difference->command_index + 1), *difference,
            seed, testing::deep_book_generator_version);
        FAIL() << "first mismatch at command " << difference->command_index + 1 << ": "
               << validation::difference_name(*difference) << "; prefix and full input: " << directory;
    }
    ASSERT_EQ(generated.samples.size(), commands.size());
    std::size_t prefill_count = 0, ordinary_tail = 0, in_band = 0, sparse_in_band = 0;
    std::size_t prefill_fifo = 0, prefill_levels = 0, boundary_full = 0;
    for (const auto& point : generated.samples) {
        EXPECT_LE(point.live_orders, capacity);
        if (point.phase == DeepBookPhase::Prefill) {
            ++prefill_count;
            EXPECT_EQ(point.live_orders, prefill_count);
            prefill_fifo = point.max_fifo_depth;
            prefill_levels = point.price_levels;
        } else if (point.phase == DeepBookPhase::Tail) {
            ++ordinary_tail;
            if (point.live_orders >= capacity * 80 / 100 && point.live_orders <= capacity * 95 / 100) {
                ++in_band;
                if (point.price_levels >= capacity / 2) ++sparse_in_band;
            }
            EXPECT_GT(point.maximum_price - point.minimum_price, config.max_price / 3);
        } else {
            boundary_full += point.live_orders == capacity;
        }
    }
    EXPECT_EQ(prefill_count, capacity * 85 / 100);
    EXPECT_EQ(ordinary_tail, tail_count);
    EXPECT_GE(in_band * 100, ordinary_tail * 60);
    if (distribution == DeepBookDistribution::SparseWide) {
        EXPECT_EQ(prefill_levels, prefill_count);
        EXPECT_EQ(sparse_in_band, in_band);
    } else {
        EXPECT_LE(prefill_levels, 6U);
        EXPECT_GE(prefill_fifo, prefill_count / 6);
    }
    EXPECT_GE(boundary_full, 2U); // Last accepted insertion and rejected insertion.
    EXPECT_EQ(generated.samples.back().live_orders, capacity * 85 / 100);
    for (const auto* name : {"cancel_head", "cancel_middle", "cancel_tail", "partial_maker_fills",
             "multi_price_sweep_commands", "levels_deleted", "level_rebuilds", "terminal_id_reuses",
             "wrong_owner_rejections", "duplicate_active_id_rejections", "full_capacity_rejections"}) {
        const auto found = generated.operations.find(name);
        ASSERT_NE(found, generated.operations.end()) << name;
        EXPECT_GT(found->second, 0U) << name;
        const std::string phase = std::string(name) == "full_capacity_rejections" ? "capacity_boundary." : "tail.";
        const auto phase_found = generated.operations.find(phase + name);
        ASSERT_NE(phase_found, generated.operations.end()) << phase << name;
        EXPECT_GT(phase_found->second, 0U) << phase << name;
    }
    EXPECT_EQ(generated.operations.at("full_capacity_rejections"), 1U);
    std::ofstream report(directory / "comparison.txt");
    report.exceptions(std::ios::failbit | std::ios::badbit);
    report << "result " << (::testing::Test::HasFailure() ? "failed" : "passed")
           << "\ncomparison full events, normalized snapshots and both engines' invariants after every command"
           << "\ncommands_compared " << commands.size() << "\ninput_hash " << trace::file_hash(directory / "input.trace")
           << "\nconfig_hash " << trace::file_hash(directory / "config.txt") << '\n';
}

TEST(DeepBookTest, LongFifoRoutine) {
    run_case(1000, 0x47303201ULL, DeepBookDistribution::LongFifo, 500);
}

TEST(DeepBookTest, SparseWideRoutine) {
    run_case(1000, 0x47303202ULL, DeepBookDistribution::SparseWide, 500);
}

TEST(DeepBookTest, DISABLED_ExtendedLongFifo) {
    for (const auto seed : {0x47303211ULL, 0x47303212ULL}) {
        run_case(10000, seed, DeepBookDistribution::LongFifo, 1000);
        if (::testing::Test::HasFatalFailure()) return;
    }
}

TEST(DeepBookTest, DISABLED_ExtendedSparseWide) {
    for (const auto seed : {0x47303221ULL, 0x47303222ULL}) {
        run_case(10000, seed, DeepBookDistribution::SparseWide, 1000);
        if (::testing::Test::HasFatalFailure()) return;
    }
}

TEST(DeepBookTest, SeedAndVersionAreDeterministicAndSavedSubsetReplaysIndependently) {
    const EngineConfig config{64, 1000000000, 1000000};
    for (const auto distribution : {DeepBookDistribution::LongFifo, DeepBookDistribution::SparseWide}) {
        const auto first = testing::deep_book_commands(config, 817, distribution, 64);
        EXPECT_EQ(first, testing::deep_book_commands(config, 817, distribution, 64));
        EXPECT_NE(first.commands, testing::deep_book_commands(config, 818, distribution, 64).commands);
        // A reduced trace is a standalone ordinary trace: removing commands can
        // introduce business rejections, but does not need generator state to replay.
        std::vector<Command> reduced;
        for (std::size_t index = 0; index < first.commands.size(); index += 3) reduced.push_back(first.commands[index]);
        const auto directory = evidence_root() / (std::string("replay-subset-") + testing::deep_book_distribution_name(distribution));
        std::filesystem::create_directories(directory);
        trace::write_trace(directory / "input.trace", reduced);
        trace::write_config(directory / "config.txt", config);
        EXPECT_FALSE(validation::compare(trace::read_config(directory / "config.txt"), trace::read_trace(directory / "input.trace")));
    }
}

TEST(DeepBookTest, RejectsUnsupportedGeneratorConfigurations) {
    EXPECT_THROW(testing::deep_book_commands({16, 1000000000, 1000000}, 1, DeepBookDistribution::LongFifo, 64), std::invalid_argument);
    EXPECT_THROW(testing::deep_book_commands({64, 100, 1000000}, 1, DeepBookDistribution::SparseWide, 64), std::invalid_argument);
    EXPECT_THROW(testing::deep_book_commands({64, 1000000000, 1}, 1, DeepBookDistribution::LongFifo, 64), std::invalid_argument);
    EXPECT_THROW(testing::deep_book_commands({64, 1000000000, 1000000}, 1, DeepBookDistribution::LongFifo, 8), std::invalid_argument);
}

TEST(DeepBookTest, RebuildCountExcludesAdditionsToAlreadyRebuiltLevel) {
    const EngineConfig config{32, 1000000000, 1000000};
    // This small, long-lived FIFO trace revisits deleted levels and then appends
    // more orders to them. A historical deletion flag alone overcounts rebuilds.
    const auto generated = testing::deep_book_commands(config, 1, DeepBookDistribution::LongFifo, 1024);
    ReferenceEngine oracle(config);
    std::vector<Event> events(oracle.required_event_capacity());
    std::set<std::pair<Side, Price>> before, ever_present;
    std::map<std::string, std::size_t> actual;
    for (std::size_t index = 0; index < generated.commands.size(); ++index) {
        ASSERT_EQ(oracle.process(generated.commands[index], events).status, ProcessStatus::Processed);
        const auto snapshot = oracle.snapshot();
        std::set<std::pair<Side, Price>> after;
        for (const auto& level : snapshot.bids) after.emplace(Side::Buy, level.price);
        for (const auto& level : snapshot.asks) after.emplace(Side::Sell, level.price);
        for (const auto& key : after) {
            if (!before.contains(key) && ever_present.contains(key)) {
                ++actual["level_rebuilds"];
                ++actual[std::string(testing::deep_book_phase_name(generated.samples[index].phase)) + ".level_rebuilds"];
            }
            ever_present.insert(key);
        }
        before = std::move(after);
    }
    ASSERT_GT(actual.at("level_rebuilds"), 1U);
    for (const auto& [name, count] : actual) EXPECT_EQ(generated.operations.at(name), count) << name;
}
} // namespace
} // namespace llmatch
