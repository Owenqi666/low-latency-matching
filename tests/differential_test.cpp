#include "differential.hpp"
#include "random_commands.hpp"
#include "trace_io.hpp"

#include <gtest/gtest.h>

#include <array>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

namespace llmatch {
namespace {

TEST(DifferentialTest, FixedSeedsCompareEveryEventAndSnapshot) {
    const char* setting = std::getenv("LLMATCH_LONG_DIFFERENTIAL");
    const bool long_run = setting != nullptr && std::string(setting) == "1";
    const std::size_t seeds = long_run ? 100 : 20;
    const std::size_t command_count = long_run ? 10000 : 2000;
    constexpr std::array<std::size_t, 4> capacities{1, 2, 16, 128};
    for (std::size_t index = 0; index < seeds; ++index) {
        const std::uint64_t seed = 0x4D310000ULL + index;
        const EngineConfig config{capacities[index % capacities.size()], 1000, 1000};
        SCOPED_TRACE("seed=" + std::to_string(seed) + " C=" + std::to_string(config.max_live_orders));
        const auto commands = testing::random_commands(config, seed, command_count);
        const auto difference = validation::compare(config, commands);
        if (difference) {
            const auto directory = std::filesystem::path("failures") / ("seed-" + std::to_string(seed));
            validation::save_failure(directory, config, commands, *difference, seed, testing::generator_version);
            FAIL() << "first mismatch at command " << difference->command_index + 1 << ": "
                   << validation::difference_name(*difference) << "; artifacts: " << directory;
        }
    }
    RecordProperty("seeds", static_cast<int>(seeds));
    RecordProperty("commands_per_seed", static_cast<int>(command_count));
    RecordProperty("total_commands", static_cast<int>(seeds * command_count));
    RecordProperty("capacities", "1,2,16,128");
    RecordProperty("generator", testing::generator_version);
}

TEST(DifferentialTest, GeneratorIsDeterministicAndExercisesBusinessErrors) {
    const EngineConfig config{16, 1000, 1000};
    const auto commands = testing::random_commands(config, 817, 2000);
    EXPECT_EQ(commands, testing::random_commands(config, 817, 2000));
    std::array<std::size_t, 3> kinds{};
    bool invalid_side = false, zero_client = false, zero_qty = false;
    for (const auto& command : commands) {
        ++kinds[static_cast<std::size_t>(command_kind(command))];
        zero_client = zero_client || command.client == 0;
        if (const auto* limit = std::get_if<LimitOrder>(&command.payload)) {
            invalid_side = invalid_side || (limit->side != Side::Buy && limit->side != Side::Sell);
            zero_qty = zero_qty || limit->qty == 0;
        }
    }
    for (const auto count : kinds) EXPECT_GT(count, 0U);
    EXPECT_TRUE(invalid_side);
    EXPECT_TRUE(zero_client);
    EXPECT_TRUE(zero_qty);
}

TEST(DifferentialTest, FailureClassPreservesEventKindDuringReduction) {
    validation::Difference initial{};
    initial.kind = validation::DifferenceKind::EventValue;
    initial.command_index = 9;
    initial.event_kind = EventKind::Trade;
    auto candidate = initial;
    candidate.command_index = 2;
    EXPECT_TRUE(validation::same_failure_kind(initial, candidate));
    candidate.event_kind = EventKind::Rejected;
    EXPECT_FALSE(validation::same_failure_kind(initial, candidate));
    candidate.kind = validation::DifferenceKind::Snapshot;
    EXPECT_FALSE(validation::same_failure_kind(initial, candidate));
}

TEST(DifferentialTest, FailureArtifactsRetainActualInputAndDetailedEvidence) {
    const auto directory = std::filesystem::path("failures") / "artifact-format-test";
    const EngineConfig config{1, 1000, 1000};
    const std::vector<Command> commands{{1, 1, LimitOrder{10, Side::Sell, 100, 7}}};
    validation::Difference difference{};
    difference.kind = validation::DifferenceKind::Snapshot;
    difference.baseline_snapshot = {{{99, 1, {{12, 2, Side::Buy, 99, 1, 1}}}}, {}};
    difference.detail = "synthetic serialization probe, not a detected engine defect";
    validation::save_failure(directory, config, commands, difference, 123, testing::generator_version);
    EXPECT_EQ(trace::read_config(directory / "config.txt"), config);
    EXPECT_EQ(trace::read_trace(directory / "input.trace"), commands);
    std::ifstream metadata(directory / "metadata.txt");
    const std::string text((std::istreambuf_iterator<char>(metadata)), std::istreambuf_iterator<char>());
    EXPECT_NE(text.find("seed 123"), std::string::npos);
    EXPECT_NE(text.find(trace::file_hash(directory / "input.trace")), std::string::npos);
    std::ifstream report(directory / "difference.txt");
    const std::string report_text((std::istreambuf_iterator<char>(report)), std::istreambuf_iterator<char>());
    EXPECT_NE(report_text.find("command_number 1"), std::string::npos);
    EXPECT_NE(report_text.find("baseline_snapshot"), std::string::npos);
    EXPECT_NE(report_text.find("reference_snapshot"), std::string::npos);
    EXPECT_NE(report_text.find("O 12 2 0 99 1 1"), std::string::npos);
    std::filesystem::remove_all(directory);
}

TEST(DifferentialTest, EmptyInputAndExpectedRejectionsAreSuccessfulComparisons) {
    const EngineConfig config{1, 1000, 1000};
    EXPECT_FALSE(validation::compare(config, {}));
    const std::vector<Command> commands{
        {0, 1, MarketOrder{1, Side::Buy, 2}},
        {1, 2, CancelOrder{99}},
        {1, 3, LimitOrder{1, Side::Sell, 100, 5}},
        {2, 4, LimitOrder{2, Side::Buy, 100, 5}},
        {2, 5, CancelOrder{1}}
    };
    EXPECT_FALSE(validation::compare(config, commands));
}

}
}
