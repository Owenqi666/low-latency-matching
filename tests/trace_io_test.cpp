#include "trace_io.hpp"
#include <gtest/gtest.h>

#include <chrono>
#include <fstream>
#include <iterator>
#include <limits>
#include <locale>
#include <sstream>

namespace {
using namespace llmatch;

class TraceIO : public ::testing::Test {
protected:
    void SetUp() override {
        directory = std::filesystem::temp_directory_path() /
            ("llmatch-trace-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
        std::filesystem::create_directory(directory);
        path = directory / "input.txt";
    }
    void TearDown() override {
        std::error_code ignored;
        std::filesystem::remove_all(directory, ignored);
    }
    void put(const std::string& text) const {
        std::ofstream output(path, std::ios::binary);
        output << text;
        ASSERT_TRUE(output.good());
    }
    std::string get() const {
        std::ifstream input(path, std::ios::binary);
        return {std::istreambuf_iterator<char>(input), {}};
    }
    void invalid_trace(const std::string& text, const std::string& diagnostic) const {
        put(text);
        try {
            (void)trace::read_trace(path);
            FAIL() << "accepted invalid trace: " << text;
        } catch (const std::runtime_error& error) {
            EXPECT_NE(std::string(error.what()).find(path.string() + ":" + diagnostic), std::string::npos)
                << error.what();
        }
    }
    std::filesystem::path directory;
    std::filesystem::path path;
};

TEST_F(TraceIO, ConfigurationRoundTripAndStrictRecordCount) {
    const EngineConfig config{32, 10000, 99};
    trace::write_config(path, config);
    EXPECT_EQ(get(), "LLMATCH_CONFIG 1\n32 10000 99\n");
    EXPECT_EQ(trace::read_config(path), config);

    put("# config\n\nLLMATCH_CONFIG 1\r\n 32\t10000 99\r\n # end\n");
    EXPECT_EQ(trace::read_config(path), config);
    for (const std::string text : {
             "LLMATCH_CONFIG 2\n32 10000 99\n",
             "LLMATCH_CONFIG 1\n",
             "LLMATCH_CONFIG 1\n32 10000\n",
             "LLMATCH_CONFIG 1\n32 10000 99 extra\n",
             "LLMATCH_CONFIG 1\n32 10000 99\n32 10000 99\n"}) {
        put(text);
        EXPECT_THROW(trace::read_config(path), std::runtime_error) << text;
    }
}

TEST_F(TraceIO, CommandsRoundTripIncludingRepresentableBusinessErrors) {
    const std::vector<Command> commands{
        {1, 10, LimitOrder{20, Side::Sell, 100, 5}},
        {2, 11, MarketOrder{21, Side::Buy, 9}},
        {1, 12, CancelOrder{20}},
        {0, 0, LimitOrder{0, static_cast<Side>(255), std::numeric_limits<Price>::min(), 0}},
        {std::numeric_limits<ClientId>::max(), std::numeric_limits<RequestId>::max(),
         MarketOrder{std::numeric_limits<OrderId>::max(), static_cast<Side>(2), std::numeric_limits<Quantity>::max()}}
    };
    trace::write_trace(path, commands);
    EXPECT_EQ(trace::read_trace(path), commands);
    EXPECT_EQ(get(),
        "LLMATCH_TRACE 1\n"
        "L 1 10 20 1 100 5\n"
        "M 2 11 21 0 9\n"
        "C 1 12 20\n"
        "L 0 0 0 255 -9223372036854775808 0\n"
        "M 4294967295 18446744073709551615 18446744073709551615 2 18446744073709551615\n");
    put("# trace\n\nLLMATCH_TRACE 1\r\n M 2 11 21 0 9 \r\n# end\n");
    EXPECT_EQ(trace::read_trace(path), (std::vector<Command>{{2, 11, MarketOrder{21, Side::Buy, 9}}}));
    trace::write_trace(path, {});
    EXPECT_TRUE(trace::read_trace(path).empty());
}

TEST_F(TraceIO, MalformedInputNamesPathAndPhysicalLine) {
    invalid_trace("LLMATCH_TRACE 2\n", "1:");
    invalid_trace("LLMATCH_TRACE 1 extra\n", "1:");
    invalid_trace("# comment\n\nLLMATCH_TRACE 1\n# command comment\nL 1 1 1 0 100\n", "5:");
    invalid_trace("LLMATCH_TRACE 1\nC 1 2 3 extra\n", "2:");
    invalid_trace("LLMATCH_TRACE 1\nC 1 2 3 # inline comments are not allowed\n", "2:");
    invalid_trace("LLMATCH_TRACE 1\nX 1 2 3\n", "2:");
    invalid_trace("# empty\n", "1:");
}

TEST_F(TraceIO, IntegerOverflowSignsAndSuffixesAreNotTruncated) {
    for (const std::string record : {
             "C 4294967296 1 1",                         // uint32 overflow
             "C 1 18446744073709551616 1",               // uint64 overflow
             "C 1 1 -1",                               // unsigned negative
             "C +1 1 1",                               // unsupported plus sign
             "M 1 1 1 256 1",                          // uint8 overflow
             "M 1 1 1 -1 1",                           // unsigned side negative
             "M 1 1 1 0 1tail",                         // trailing characters
             "M 1 1 1 0 1.0",                           // floating-point text
             "L 1 1 1 0 9223372036854775808 1",          // int64 positive overflow
             "L 1 1 1 0 -9223372036854775809 1"}) {      // int64 negative overflow
        invalid_trace("LLMATCH_TRACE 1\n" + record + "\n", "2:");
    }
}

class GroupedNumbers : public std::numpunct<char> {
    char do_thousands_sep() const override { return ','; }
    std::string do_grouping() const override { return "\3"; }
};

TEST_F(TraceIO, EventOutputIncludesAllFieldsInStableOrderWithoutLocaleGrouping) {
    Event event{};
    event.kind = EventKind::Trade;
    event.command_kind = CommandKind::Market;
    event.command_seq = 1000;
    event.event_seq = 2000;
    event.client = 3;
    event.request = 4;
    event.order_id = 5;
    event.reject_reason = RejectReason::InvalidClientId;
    event.cancel_reason = CancelReason::UserCancel;
    event.completion = CompletionStatus::Accepted;
    event.side = Side::Sell;
    event.price = -10;
    event.qty = 11;
    event.arrival_seq = 12;
    event.maker_id = 13;
    event.taker_id = 14;
    event.maker_client = 15;
    event.taker_client = 16;
    event.maker_arrival_seq = 17;
    event.taker_arrival_seq = 18;
    event.filled_qty = 19;
    event.resting_qty = 20;
    event.cancelled_qty = 21;
    std::ostringstream output;
    output.imbue(std::locale(std::locale::classic(), new GroupedNumbers));
    trace::write_events(output, std::span(&event, 1));
    EXPECT_EQ(output.str(), "E 2 1 1000 2000 3 4 5 1 1 1 1 -10 11 12 13 14 15 16 17 18 19 20 21\n");
}

TEST_F(TraceIO, SnapshotOutputPreservesCanonicalLevelsAndEveryOrderField) {
    const BookSnapshot book{
        {{99, 5, {{10, 1, Side::Buy, 99, 5, 1}}}},
        {{101, 7, {{11, 2, Side::Sell, 101, 3, 2}, {12, 3, Side::Sell, 101, 4, 3}}}}
    };
    std::ostringstream output;
    trace::write_snapshot(output, book);
    EXPECT_EQ(output.str(),
        "BOOK 1\nB 99 5 1\nO 10 1 0 99 5 1\nA 101 7 2\nO 11 2 1 101 3 2\nO 12 3 1 101 4 3\n");
    std::ostringstream empty;
    trace::write_snapshot(empty, {});
    EXPECT_EQ(empty.str(), "BOOK 1\n");
}

TEST_F(TraceIO, HashUsesKnownFnv1aVectorsAndRawBytes) {
    put("");
    EXPECT_EQ(trace::file_hash(path), "fnv1a64:cbf29ce484222325");
    put("hello");
    EXPECT_EQ(trace::file_hash(path), "fnv1a64:a430d84680aabd0b");
    put("a");
    EXPECT_EQ(trace::file_hash(path), "fnv1a64:af63dc4c8601ec8c");
    put("hello\n");
    EXPECT_NE(trace::file_hash(path), "fnv1a64:a430d84680aabd0b");
}

TEST_F(TraceIO, IoFailuresAreReported) {
    EXPECT_THROW(trace::read_trace(directory / "missing"), std::runtime_error);
    EXPECT_THROW(trace::file_hash(directory / "missing"), std::runtime_error);
    EXPECT_THROW(trace::write_trace(directory / "missing" / "output", {}), std::runtime_error);
    std::ostringstream bad;
    bad.setstate(std::ios::badbit);
    EXPECT_THROW(trace::write_events(bad, {}), std::runtime_error);
    EXPECT_THROW(trace::write_snapshot(bad, {}), std::runtime_error);
}

} // namespace
