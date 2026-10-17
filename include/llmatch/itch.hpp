#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <map>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace llmatch::itch {

struct Error : std::runtime_error {
    Error(std::string reason, std::uint64_t offset, std::uint64_t index,
          char type = '?', std::optional<std::uint64_t> reference = std::nullopt);
    std::uint64_t offset;
    std::uint64_t message_index;
    char type;
    std::optional<std::uint64_t> reference;
    std::string type_label() const;
};

struct Message {
    char type{};
    std::uint16_t stock_locate{};
    std::uint16_t tracking_number{};
    std::uint64_t timestamp{};
    std::uint64_t offset{};
    std::uint64_t message_index{};
    std::uint64_t reference{};
    std::uint64_t new_reference{};
    std::uint64_t match_number{};
    std::uint32_t shares{};
    std::uint32_t price{};
    char side{};
    char event{};
    char printable{};
    std::string symbol;
    std::string attribution;
    bool ignored{};
};

std::size_t payload_size(char type); // Zero means an unsupported type.
Message decode(std::span<const std::uint8_t> payload, std::uint64_t offset = 0,
               std::uint64_t message_index = 0);

class BinaryFileReader {
public:
    using Handler = std::function<void(const Message&)>;
    void feed(std::span<const std::uint8_t> bytes, const Handler& handler);
    void finish() const;
    std::uint64_t bytes() const { return bytes_; }
    std::uint64_t messages() const { return messages_; }
    std::uint64_t last_offset() const { return last_offset_; }
    bool ended() const { return ended_; }
    std::string input_hash() const;
private:
    std::array<std::uint8_t, 2> length_{};
    std::size_t length_used_{};
    std::size_t expected_{};
    std::vector<std::uint8_t> partial_;
    std::uint64_t bytes_{};
    std::uint64_t messages_{};
    std::uint64_t last_offset_{};
    std::uint64_t hash_{14695981039346656037ULL};
    bool ended_{};
};

struct Order {
    std::uint64_t reference{};
    char side{};
    std::uint32_t price{};
    std::uint32_t shares{};
    std::string attribution;
    bool operator==(const Order&) const = default;
};

struct Level {
    char side{};
    std::uint32_t price{};
    std::uint64_t shares{};
    std::uint64_t orders{};
    bool operator==(const Level&) const = default;
};

struct Bbo {
    std::optional<Level> bid;
    std::optional<Level> ask;
    bool operator==(const Bbo&) const = default;
};

struct Statistics {
    std::uint64_t messages{};
    std::uint64_t target_messages{};
    std::uint64_t updates{};
    std::uint64_t filtered_messages{};
    std::map<char, std::uint64_t> counts_by_type;
    std::map<char, std::uint64_t> ignored_by_type;
    std::string system_events;
};

class Reconstructor {
public:
    explicit Reconstructor(std::string symbol, std::size_t max_orders = 1'000'000);
    bool apply(const Message& message);
    void finish(bool binary_end, bool allow_prefix) const;
    const Order* find(std::uint64_t reference) const;
    Level level(char side, std::uint32_t price) const;
    Bbo bbo() const;
    std::vector<Order> orders() const;
    std::vector<Level> levels() const;
    const Statistics& statistics() const { return statistics_; }
    const std::string& symbol() const { return symbol_; }
    std::optional<std::uint16_t> stock_locate() const { return locate_; }
    bool itch_end() const { return ended_; }
    std::size_t size() const { return orders_.size(); }
    void check_invariants() const;
private:
    using Levels = std::map<std::uint32_t, Level>;
    Levels& side_levels(char side);
    const Levels& side_levels(char side) const;
    void remove(const Order& order);
    void add(const Order& order);
    std::string symbol_;
    std::size_t max_orders_;
    std::optional<std::uint16_t> locate_;
    std::unordered_map<std::uint16_t, std::string> directories_;
    std::unordered_map<std::uint64_t, Order> orders_;
    Levels bids_;
    Levels asks_;
    Statistics statistics_;
    bool started_{};
    bool ended_{};
    std::uint64_t last_offset_{};
};

} // namespace llmatch::itch
