#include "llmatch/itch.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <limits>
#include <string>
#include <vector>

namespace llmatch::itch {
namespace {

Message event(char code) {
    Message m;
    m.type = 'S';
    m.event = code;
    return m;
}

Message directory(std::string symbol = "TEST", std::uint16_t locate = 7) {
    Message m;
    m.type = 'R';
    m.symbol = std::move(symbol);
    m.stock_locate = locate;
    return m;
}

Message update(char type, std::uint64_t reference, std::uint32_t shares = 0,
               std::uint32_t price = 10000, char side = 'B') {
    Message m;
    m.type = type;
    m.stock_locate = 7;
    m.reference = reference;
    m.shares = shares;
    m.price = price;
    m.side = side;
    m.symbol = "TEST";
    m.printable = 'Y';
    return m;
}

void begin(Reconstructor& book) {
    ASSERT_FALSE(book.apply(event('O')));
    ASSERT_FALSE(book.apply(directory()));
}

std::vector<std::uint8_t> raw_event(char code) {
    return {'S', 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, static_cast<std::uint8_t>(code)};
}

void frame(std::vector<std::uint8_t>& stream, const std::vector<std::uint8_t>& payload) {
    stream.push_back(static_cast<std::uint8_t>(payload.size() >> 8U));
    stream.push_back(static_cast<std::uint8_t>(payload.size()));
    stream.insert(stream.end(), payload.begin(), payload.end());
}

TEST(ItchDecodeTest, IndependentGoldenBytesDecodeWideFieldsAndAttribution) {
    // Handwritten wire bytes, not produced by the decoder or a production encoder.
    const std::vector<std::uint8_t> bytes{
        'F', 0x12, 0x34, 0xab, 0xcd, 1, 2, 3, 4, 5, 6,
        0xfe, 0xdc, 0xba, 0x98, 0x76, 0x54, 0x32, 0x10,
        'S', 1, 2, 3, 4, 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H',
        0x07, 0x5b, 0xcd, 0x15, 'N', 'S', 'D', 'Q'};
    const auto m = decode(bytes, 321, 9);
    EXPECT_EQ(m.type, 'F');
    EXPECT_EQ(m.stock_locate, 0x1234);
    EXPECT_EQ(m.tracking_number, 0xabcd);
    EXPECT_EQ(m.timestamp, 0x010203040506ULL);
    EXPECT_EQ(m.reference, 0xfedcba9876543210ULL);
    EXPECT_EQ(m.shares, 0x01020304U);
    EXPECT_EQ(m.price, 123456789U);
    EXPECT_EQ(m.side, 'S');
    EXPECT_EQ(m.symbol, "ABCDEFGH");
    EXPECT_EQ(m.attribution, "NSDQ");
    EXPECT_EQ(m.offset, 321U);
    EXPECT_EQ(m.message_index, 9U);
    EXPECT_FALSE(m.ignored);
}

TEST(ItchDecodeTest, UnknownAndWrongLengthFailBeforeAnyFiltering) {
    const std::vector<std::uint8_t> unknown{'?', 0xff, 0xff};
    EXPECT_THROW(decode(unknown), Error);
    try { decode(std::vector<std::uint8_t>{0xff}); FAIL() << "unknown binary type should fail"; }
    catch (const Error& error) {
        EXPECT_EQ(error.type_label(), "0xff");
        EXPECT_NE(std::string(error.what()).find("type=0xff"), std::string::npos);
        for (const char c : std::string(error.what())) EXPECT_GE(static_cast<unsigned char>(c), 32U);
        for (const char c : std::string(error.what())) EXPECT_LE(static_cast<unsigned char>(c), 126U);
    }
    auto bytes = raw_event('O');
    bytes.push_back(0);
    EXPECT_THROW(decode(bytes), Error);
    bytes.pop_back();
    bytes[2] = 1;
    EXPECT_THROW(decode(bytes), Error);
    bytes[2] = 0;
    bytes[11] = '?';
    EXPECT_THROW(decode(bytes), Error);
    bytes[11] = 'O';
    std::fill(bytes.begin() + 5, bytes.begin() + 11, 0xff);
    EXPECT_THROW(decode(bytes), Error);
}

TEST(ItchDecodeTest, KnownNonBookTypesHaveExplicitFixedSizesAndNoMutation) {
    const std::vector<std::pair<char, std::size_t>> expected{
        {'H',25}, {'Y',20}, {'L',26}, {'V',35}, {'W',12}, {'K',28}, {'J',35},
        {'h',21}, {'P',44}, {'Q',40}, {'B',19}, {'I',50}, {'N',20}, {'O',48}};
    Reconstructor book("TEST");
    begin(book);
    book.apply(update('A', 1, 9));
    const auto initial = book.orders();
    for (const auto& [type, size] : expected) {
        SCOPED_TRACE(type);
        std::vector<std::uint8_t> bytes(size, 0);
        bytes[0] = static_cast<std::uint8_t>(type);
        bytes[2] = 7;
        const auto m = decode(bytes);
        EXPECT_TRUE(m.ignored);
        EXPECT_FALSE(book.apply(m));
        bytes.pop_back();
        EXPECT_THROW(decode(bytes), Error);
    }
    EXPECT_EQ(book.orders(), initial);
    EXPECT_EQ(book.statistics().ignored_by_type.size(), expected.size());
    EXPECT_EQ(book.statistics().updates, 1U);
}

TEST(ItchFramingTest, EverySplitAndByteChunksPreserveOffsetsAndHash) {
    std::vector<std::uint8_t> bytes;
    frame(bytes, raw_event('O'));
    frame(bytes, raw_event('C'));
    frame(bytes, {});
    BinaryFileReader whole;
    whole.feed(bytes, [](const Message&) {});
    ASSERT_TRUE(whole.ended());
    for (std::size_t split = 0; split <= bytes.size(); ++split) {
        SCOPED_TRACE(split);
        BinaryFileReader reader;
        std::vector<Message> messages;
        const auto handler = [&](const Message& m) { messages.push_back(m); };
        reader.feed(std::span(bytes).first(split), handler);
        reader.feed(std::span(bytes).subspan(split), handler);
        EXPECT_NO_THROW(reader.finish());
        ASSERT_EQ(messages.size(), 2U);
        EXPECT_EQ(messages[0].offset, 0U);
        EXPECT_EQ(messages[0].message_index, 1U);
        EXPECT_EQ(messages[1].offset, 14U);
        EXPECT_EQ(messages[1].message_index, 2U);
        EXPECT_EQ(reader.last_offset(), 28U);
        EXPECT_EQ(reader.messages(), 2U);
        EXPECT_EQ(reader.bytes(), 30U);
        EXPECT_EQ(reader.input_hash(), whole.input_hash());
        EXPECT_TRUE(reader.ended());
    }
    BinaryFileReader singles;
    for (std::size_t i = 0; i < bytes.size(); ++i) singles.feed(std::span(bytes).subspan(i, 1), [](const Message&) {});
    EXPECT_EQ(singles.input_hash(), whole.input_hash());
    EXPECT_NO_THROW(singles.finish());
}

TEST(ItchFramingTest, PrefixBoundaryDoesNotPermitHalfHeaderOrHalfPayload) {
    std::vector<std::uint8_t> bytes;
    frame(bytes, raw_event('O'));
    BinaryFileReader prefix;
    prefix.feed(bytes, [](const Message&) {});
    EXPECT_NO_THROW(prefix.finish());
    EXPECT_FALSE(prefix.ended());
    bytes.push_back(0);
    BinaryFileReader half_header;
    half_header.feed(bytes, [](const Message&) {});
    try { half_header.finish(); FAIL() << "expected truncated header"; }
    catch (const Error& e) { EXPECT_EQ(e.offset, 14U); EXPECT_EQ(e.message_index, 2U); }
    bytes.push_back(12);
    bytes.push_back('S');
    BinaryFileReader half_payload;
    half_payload.feed(bytes, [](const Message&) {});
    try { half_payload.finish(); FAIL() << "expected truncated payload"; }
    catch (const Error& e) { EXPECT_EQ(e.offset, 14U); EXPECT_EQ(e.type, 'S'); }
}

TEST(ItchFramingTest, ZeroLengthIsEndAndTrailingBytesAlwaysFail) {
    BinaryFileReader reader;
    const std::vector<std::uint8_t> marker{0, 0};
    int callbacks = 0;
    reader.feed(marker, [&](const Message&) { ++callbacks; });
    EXPECT_TRUE(reader.ended());
    EXPECT_EQ(callbacks, 0);
    EXPECT_NO_THROW(reader.finish());
    EXPECT_THROW(reader.feed(std::span(marker).first(1), [](const Message&) {}), Error);
    BinaryFileReader together;
    const std::vector<std::uint8_t> trailing{0, 0, 0};
    EXPECT_THROW(together.feed(trailing, [](const Message&) {}), Error);
}

TEST(ItchBookTest, VisibleLifecycleUsesReferencesAndNonPrintableExecutionStillReduces) {
    Reconstructor book("TEST");
    begin(book);
    auto attributed = update('F', 10, 12, 10100, 'S');
    attributed.attribution = "ABCD";
    book.apply(attributed);
    book.apply(update('A', 20, 8, 10100, 'S'));
    book.apply(update('A', 30, 5, 9900));
    book.apply(update('E', 10, 2));
    auto nonprintable = update('C', 10, 3, 7777);
    nonprintable.printable = 'N';
    book.apply(nonprintable);
    ASSERT_NE(book.find(10), nullptr);
    EXPECT_EQ(*book.find(10), (Order{10, 'S', 10100, 7, "ABCD"}));
    EXPECT_EQ(book.level('S', 10100), (Level{'S', 10100, 15, 2}));
    book.apply(update('X', 20, 8));
    EXPECT_EQ(book.find(20), nullptr);
    auto replacement = update('U', 10, 4, 10200);
    replacement.new_reference = 40;
    book.apply(replacement);
    EXPECT_EQ(book.find(10), nullptr);
    ASSERT_NE(book.find(40), nullptr);
    EXPECT_EQ(*book.find(40), (Order{40, 'S', 10200, 4, "ABCD"}));
    EXPECT_EQ(book.bbo(), (Bbo{Level{'B',9900,5,1}, Level{'S',10200,4,1}}));
    book.apply(update('E', 40, 4));
    book.apply(update('D', 30));
    EXPECT_EQ(book.size(), 0U);
    EXPECT_EQ(book.bbo(), Bbo{});
    EXPECT_NO_THROW(book.check_invariants());
}

TEST(ItchBookTest, ReplacementAtCapacityUsesNewTotalAndPreservesSamePriceAggregate) {
    Reconstructor book("TEST", 2);
    begin(book);
    book.apply(update('A', 1, 5));
    book.apply(update('A', 2, 7));
    auto replace = update('U', 1, 9);
    replace.new_reference = 3;
    EXPECT_TRUE(book.apply(replace));
    EXPECT_EQ(book.size(), 2U);
    EXPECT_EQ(book.level('B', 10000), (Level{'B',10000,16,2}));
    EXPECT_EQ(book.find(1), nullptr);
    EXPECT_EQ(book.find(3)->shares, 9U);
    EXPECT_NO_THROW(book.check_invariants());
}

TEST(ItchBookTest, InvalidBusinessUpdatesLeaveOrdersAndLevelsUnchanged) {
    Reconstructor book("TEST", 2);
    begin(book);
    book.apply(update('A', 1, 8));
    book.apply(update('A', 2, 7, 10100, 'S'));
    std::vector<Message> invalid{update('A',1,1), update('A',3,1), update('D',999),
                                 update('E',1,9), update('X',1,0), update('A',4,1,10000,'?')};
    auto conflict = update('U',1,4,10200); conflict.new_reference = 2; invalid.push_back(conflict);
    auto self = update('U',1,4); self.new_reference = 1; invalid.push_back(self);
    auto zero = update('U',1,0); zero.new_reference = 3; invalid.push_back(zero);
    auto bad_flag = update('C',1,4); bad_flag.printable = '?'; invalid.push_back(bad_flag);
    auto bad_price = update('C',1,4,2'000'000'001); invalid.push_back(bad_price);
    const auto orders = book.orders();
    const auto levels = book.levels();
    for (const auto& m : invalid) {
        SCOPED_TRACE(m.type);
        EXPECT_THROW(book.apply(m), Error);
        EXPECT_EQ(book.orders(), orders);
        EXPECT_EQ(book.levels(), levels);
        EXPECT_EQ(book.statistics().updates, 2U);
        EXPECT_NO_THROW(book.check_invariants());
    }
}

TEST(ItchBookTest, OtherSecuritiesAreFilteredWithoutCreatingOrdersOrValidatingTheirBusinessFields) {
    Reconstructor book("TEST");
    begin(book);
    EXPECT_FALSE(book.apply(directory("OTHER", 9)));
    auto unrelated = update('A', 1, 0, std::numeric_limits<std::uint32_t>::max(), '?');
    unrelated.stock_locate = 9;
    unrelated.symbol = "OTHER";
    EXPECT_FALSE(book.apply(unrelated));
    unrelated.type = 'E';
    unrelated.reference = 999;
    EXPECT_FALSE(book.apply(unrelated));
    EXPECT_EQ(book.size(), 0U);
    EXPECT_EQ(book.statistics().filtered_messages, 3U);
    EXPECT_THROW(book.apply(update('E',999,1)), Error);
}

TEST(ItchBookTest, DirectoryAndSessionContextCannotBeInventedOrChanged) {
    Reconstructor prior_conflict("TEST");
    prior_conflict.apply(event('O'));
    prior_conflict.apply(directory("OTHER", 7));
    EXPECT_THROW(prior_conflict.apply(directory()), Error);
    EXPECT_FALSE(prior_conflict.stock_locate());
    Reconstructor missing("TEST");
    EXPECT_THROW(missing.apply(directory()), Error);
    missing.apply(event('O'));
    EXPECT_THROW(missing.apply(update('A',1,1)), Error);
    missing.apply(directory());
    EXPECT_THROW(missing.apply(directory("TEST",8)), Error);
    EXPECT_THROW(missing.apply(directory("OTHER",7)), Error);
    auto wrong_symbol = update('A',1,1); wrong_symbol.symbol = "OTHER";
    EXPECT_THROW(missing.apply(wrong_symbol), Error);
    EXPECT_THROW(missing.apply(event('O')), Error);
    EXPECT_THROW(missing.finish(false,true), Error); // Directory-only capture is not useful coverage.
    EXPECT_EQ(missing.size(), 0U);
}

TEST(ItchBookTest, SessionCompletenessIsSeparateFromValidDayStartPrefix) {
    Reconstructor book("TEST");
    begin(book);
    book.apply(update('A',1,1));
    EXPECT_NO_THROW(book.finish(false,true));
    EXPECT_THROW(book.finish(false,false), Error);
    EXPECT_THROW(book.finish(true,true), Error); // Cannot fabricate a BinaryFILE end before S/C.
    book.apply(event('E'));
    EXPECT_TRUE(book.apply(update('D',1))); // Deletes can follow End of System Hours.
    book.apply(event('C'));
    EXPECT_NO_THROW(book.finish(true,false));
    EXPECT_NO_THROW(book.finish(false,true));
    EXPECT_THROW(book.apply(update('A',2,1)), Error);
}

TEST(ItchBookTest, IntegerDomainAndCanonicalSnapshotsDoNotUseMatchingPriceLimits) {
    Reconstructor book("TEST");
    begin(book);
    const auto maximum = std::numeric_limits<std::uint32_t>::max();
    book.apply(update('A',std::numeric_limits<std::uint64_t>::max(),maximum,0));
    book.apply(update('A',0,maximum,0));
    book.apply(update('A',3,1,2'000'000'000));
    book.apply(update('A',2,5,1,'S')); // Crossed display is preserved; no synthetic matching.
    EXPECT_EQ(book.level('B',0).shares, 8'589'934'590ULL);
    ASSERT_EQ(book.orders().size(), 4U);
    EXPECT_EQ(book.orders()[0].reference, 0U);
    EXPECT_EQ(book.levels()[0].price, 2'000'000'000U);
    EXPECT_EQ(book.levels()[1].price, 0U);
    EXPECT_EQ(book.levels()[2].side, 'S');
    EXPECT_THROW(book.apply(update('A',4,1,2'000'000'001)), Error);
    EXPECT_NO_THROW(book.check_invariants());
}

TEST(ItchBookTest, BestLevelRemovalExposesNextPriceWithoutScanningOrders) {
    Reconstructor book("TEST");
    begin(book);
    book.apply(update('A',1,5,10000));
    book.apply(update('A',2,7,10000));
    book.apply(update('A',3,11,9900));
    book.apply(update('D',1));
    EXPECT_EQ(book.bbo().bid, (Level{'B',10000,7,1}));
    book.apply(update('D',2));
    EXPECT_EQ(book.bbo().bid, (Level{'B',9900,11,1}));
    EXPECT_EQ(book.level('B',10000), (Level{'B',10000,0,0}));
    EXPECT_NO_THROW(book.check_invariants());
}

} // namespace
} // namespace llmatch::itch
