#include "llmatch/order_book.hpp"

#include <gtest/gtest.h>

#include <limits>
#include <type_traits>

namespace llmatch {
namespace {

static_assert(!std::is_copy_constructible_v<OrderBook>);
static_assert(!std::is_move_constructible_v<OrderBook>);

TEST(OrderBookTest, BestPricesAndSnapshotAreCanonical) {
    OrderBook book(8);
    book.insert_resting({1, 1, Side::Buy, 97, 3, 1});
    book.insert_resting({2, 2, Side::Buy, 99, 5, 2});
    book.insert_resting({3, 3, Side::Sell, 103, 7, 3});
    book.insert_resting({4, 4, Side::Sell, 101, 11, 4});
    book.insert_resting({5, 5, Side::Buy, 99, 13, 5});
    book.insert_resting({6, 6, Side::Sell, 101, 17, 6});
    ASSERT_NE(book.best_opposite(Side::Sell), nullptr);
    ASSERT_NE(book.best_opposite(Side::Buy), nullptr);
    EXPECT_EQ(book.best_opposite(Side::Sell)->id, 2U);
    EXPECT_EQ(book.best_opposite(Side::Buy)->id, 4U);
    const auto snapshot = book.snapshot();
    ASSERT_EQ(snapshot.bids.size(), 2U);
    ASSERT_EQ(snapshot.asks.size(), 2U);
    EXPECT_EQ(snapshot.bids[0], (LevelSnapshot{99, 18, {{2, 2, Side::Buy, 99, 5, 2},
                                                      {5, 5, Side::Buy, 99, 13, 5}}}));
    EXPECT_EQ(snapshot.bids[1].price, 97);
    EXPECT_EQ(snapshot.asks[0], (LevelSnapshot{101, 28, {{4, 4, Side::Sell, 101, 11, 4},
                                                       {6, 6, Side::Sell, 101, 17, 6}}}));
    EXPECT_EQ(snapshot.asks[1].price, 103);
    EXPECT_EQ(book.size(), 6U);
    EXPECT_NO_THROW(book.check_invariants());
}

TEST(OrderBookTest, RemovesMiddleHeadTailAndLastNodeOnEitherSide) {
    for (const Side side : {Side::Buy, Side::Sell}) {
        OrderBook book(5);
        for (OrderId id = 1; id <= 5; ++id) {
            book.insert_resting({id, 1, side, 100, id, id});
        }
        EXPECT_EQ(book.erase_resting(3), 3U); // middle
        EXPECT_NO_THROW(book.check_invariants());
        EXPECT_EQ(book.erase_resting(1), 1U); // head
        EXPECT_NO_THROW(book.check_invariants());
        EXPECT_EQ(book.erase_resting(5), 5U); // tail
        EXPECT_NO_THROW(book.check_invariants());
        const auto snapshot = book.snapshot();
        const auto& levels = side == Side::Buy ? snapshot.bids : snapshot.asks;
        ASSERT_EQ(levels.size(), 1U);
        EXPECT_EQ(levels[0].total_qty, 6U);
        ASSERT_EQ(levels[0].orders.size(), 2U);
        EXPECT_EQ(levels[0].orders[0].id, 2U);
        EXPECT_EQ(levels[0].orders[1].id, 4U);
        for (const OrderId id : {1U, 3U, 5U}) EXPECT_EQ(book.find(id), nullptr);
        EXPECT_EQ(book.erase_resting(2), 2U);
        EXPECT_EQ(book.erase_resting(4), 4U); // final node also removes level
        EXPECT_EQ(book.size(), 0U);
        EXPECT_EQ(book.best_opposite(Side::Buy), nullptr);
        EXPECT_EQ(book.best_opposite(Side::Sell), nullptr);
        EXPECT_EQ(book.snapshot(), BookSnapshot{});
        EXPECT_NO_THROW(book.check_invariants());
    }
}

TEST(OrderBookTest, PartialFillKeepsFifoAndCompleteFillRemovesIndexAndLevel) {
    OrderBook book(3);
    book.insert_resting({10, 1, Side::Sell, 100, 8, 1});
    book.insert_resting({11, 2, Side::Sell, 100, 4, 2});
    book.insert_resting({12, 3, Side::Sell, 101, 2, 3});
    book.apply_fill(10, 3);
    ASSERT_NE(book.find(10), nullptr);
    EXPECT_EQ(book.find(10)->remaining, 5U);
    EXPECT_EQ(book.best_opposite(Side::Buy)->id, 10U);
    EXPECT_EQ(book.snapshot().asks[0].total_qty, 9U);
    EXPECT_NO_THROW(book.check_invariants());
    book.apply_fill(10, 5);
    EXPECT_EQ(book.find(10), nullptr);
    EXPECT_EQ(book.best_opposite(Side::Buy)->id, 11U);
    EXPECT_EQ(book.snapshot().asks[0].total_qty, 4U);
    EXPECT_NO_THROW(book.check_invariants());
    book.apply_fill(11, 4);
    EXPECT_EQ(book.find(11), nullptr);
    EXPECT_EQ(book.best_opposite(Side::Buy)->id, 12U);
    ASSERT_EQ(book.snapshot().asks.size(), 1U);
    EXPECT_NO_THROW(book.check_invariants());
    book.apply_fill(12, 2);
    EXPECT_EQ(book.snapshot(), BookSnapshot{});
    EXPECT_NO_THROW(book.check_invariants());
}

TEST(OrderBookTest, ErasingBestBidAndAskRevealsNextPrice) {
    OrderBook book(4);
    book.insert_resting({1, 1, Side::Buy, 98, 1, 1});
    book.insert_resting({2, 1, Side::Buy, 99, 1, 2});
    book.insert_resting({3, 1, Side::Sell, 101, 1, 3});
    book.insert_resting({4, 1, Side::Sell, 102, 1, 4});
    book.apply_fill(2, 1);
    book.erase_resting(3);
    EXPECT_EQ(book.best_opposite(Side::Sell)->price, 98);
    EXPECT_EQ(book.best_opposite(Side::Buy)->price, 102);
    EXPECT_NO_THROW(book.check_invariants());
}

TEST(OrderBookTest, LargeAggregatesDoNotWrap) {
    const Quantity maximum = std::numeric_limits<Quantity>::max();
    OrderBook book(3);
    book.insert_resting({1, 1, Side::Buy, 100, maximum - 4, 1});
    book.insert_resting({2, 1, Side::Buy, 100, 4, 2});
    EXPECT_EQ(book.snapshot().bids[0].total_qty, maximum);
    EXPECT_NO_THROW(book.check_invariants());
    EXPECT_THROW(book.insert_resting({3, 1, Side::Buy, 100, 1, 3}), std::overflow_error);
    EXPECT_EQ(book.size(), 2U);
    EXPECT_NO_THROW(book.check_invariants());
    book.apply_fill(1, maximum - 5);
    EXPECT_EQ(book.snapshot().bids[0].total_qty, 5U);
    EXPECT_EQ(book.erase_resting(2), 4U);
    book.apply_fill(1, 1);
    EXPECT_EQ(book.size(), 0U);
    EXPECT_NO_THROW(book.check_invariants());
}

TEST(OrderBookTest, IndexSurvivesRehashAndRepeatedNodeReuse) {
    // Storage has no admission policy: a small reserve forces rehash while
    // inserting many nodes, exposing incorrectly retained hash iterators.
    OrderBook book(1);
    constexpr OrderId count = 256;
    for (OrderId id = 1; id <= count; ++id) {
        book.insert_resting({id, 1, Side::Buy, static_cast<Price>(id % 16 + 1), 2, id});
    }
    EXPECT_NO_THROW(book.check_invariants());
    for (OrderId id = 2; id <= count; id += 2) book.erase_resting(id);
    EXPECT_NO_THROW(book.check_invariants());
    for (OrderId id = 1; id <= count; id += 2) {
        book.apply_fill(id, 1);
        book.apply_fill(id, 1);
    }
    EXPECT_EQ(book.size(), 0U);
    EXPECT_NO_THROW(book.check_invariants());
    for (OrderId id = 1; id <= count; ++id) {
        book.insert_resting({id, 2, Side::Sell, 101, 1, count + id});
    }
    EXPECT_NO_THROW(book.check_invariants());
    for (OrderId id = 1; id <= count; ++id) book.apply_fill(id, 1);
    EXPECT_EQ(book.snapshot(), BookSnapshot{});
    EXPECT_NO_THROW(book.check_invariants());
}

TEST(OrderBookTest, InvariantChecksRemainActiveWithoutDebugAssertions) {
    OrderBook book(2);
    book.insert_resting({1, 1, Side::Buy, 100, 1, 2});
    book.insert_resting({2, 1, Side::Buy, 100, 1, 1});
    EXPECT_THROW(book.check_invariants(), std::logic_error);
}

}
}
