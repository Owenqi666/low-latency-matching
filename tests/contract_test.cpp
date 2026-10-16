#include "llmatch/types.hpp"
#include "llmatch/command.hpp"
#include "llmatch/event.hpp"
#include "llmatch/snapshot.hpp"
#include <gtest/gtest.h>
#include <limits>

TEST(Contract, IntegerDomains) {
    EXPECT_EQ(std::numeric_limits<llmatch::Price>::digits, 63);
    EXPECT_EQ(std::numeric_limits<llmatch::Quantity>::digits, 64);
    EXPECT_TRUE(std::numeric_limits<llmatch::Price>::is_signed);
    EXPECT_FALSE(std::numeric_limits<llmatch::Quantity>::is_signed);
}

TEST(Contract, CommandsCarryOnlyRelevantFields) {
    const llmatch::Command limit{1, 2, llmatch::LimitOrder{3, llmatch::Side::Buy, 100, 4}};
    const llmatch::Command market{1, 2, llmatch::MarketOrder{3, llmatch::Side::Sell, 4}};
    const llmatch::Command cancel{1, 2, llmatch::CancelOrder{3}};
    EXPECT_EQ(llmatch::command_kind(limit), llmatch::CommandKind::Limit);
    EXPECT_EQ(llmatch::command_kind(market), llmatch::CommandKind::Market);
    EXPECT_EQ(llmatch::command_kind(cancel), llmatch::CommandKind::Cancel);
    EXPECT_EQ(llmatch::order_id(cancel), 3U);
    EXPECT_TRUE(std::is_trivially_copyable_v<llmatch::Event>);
    EXPECT_EQ(llmatch::BookSnapshot{}, llmatch::BookSnapshot{});
}
