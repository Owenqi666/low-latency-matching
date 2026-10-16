#include "llmatch/types.hpp"
#include <gtest/gtest.h>
#include <limits>

TEST(Contract, IntegerDomains) {
    EXPECT_EQ(std::numeric_limits<llmatch::Price>::digits, 62);
    EXPECT_EQ(std::numeric_limits<llmatch::Quantity>::digits, 64);
    EXPECT_TRUE(std::numeric_limits<llmatch::Price>::is_signed);
    EXPECT_FALSE(std::numeric_limits<llmatch::Quantity>::is_signed);
}
