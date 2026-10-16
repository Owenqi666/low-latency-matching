#include "trace_io.hpp"

#include <array>
#include <charconv>
#include <fstream>
#include <iomanip>
#include <locale>
#include <sstream>
#include <stdexcept>
#include <type_traits>

namespace llmatch::trace {
namespace {

class Reader {
public:
    explicit Reader(const std::filesystem::path& path) : path_(path), input_(path) {
        if (!input_) fail("cannot open input");
    }

    bool next() {
        fields.clear();
        std::string line;
        while (std::getline(input_, line)) {
            ++line_;
            std::istringstream tokens(line);
            tokens.imbue(std::locale::classic());
            std::string token;
            while (tokens >> token) fields.push_back(token);
            if (fields.empty()) continue;
            if (fields.front().starts_with('#')) {
                fields.clear();
                continue;
            }
            return true;
        }
        if (input_.bad()) fail("input read failed");
        return false;
    }

    void header(const std::string& expected) {
        if (!next()) fail("missing " + expected + " header");
        if (fields.size() != 2 || fields[0] != expected || fields[1] != "1") {
            fail("expected '" + expected + " 1'");
        }
    }

    void count(std::size_t expected) const {
        if (fields.size() != expected) {
            fail("expected " + std::to_string(expected) + " fields, got " + std::to_string(fields.size()));
        }
    }

    template <class T>
    T number(std::size_t index, const char* name) const {
        const auto& field = fields[index];
        T value{};
        const auto result = std::from_chars(field.data(), field.data() + field.size(), value);
        if (result.ec != std::errc{} || result.ptr != field.data() + field.size()) {
            fail(std::string("invalid ") + name + " integer '" + field + "'");
        }
        return value;
    }

    [[noreturn]] void fail(const std::string& message) const {
        throw std::runtime_error(path_.string() + ":" + std::to_string(line_) + ": " + message);
    }

    std::vector<std::string> fields;

private:
    std::filesystem::path path_;
    std::ifstream input_;
    std::size_t line_{};
};

// to_chars keeps integer records independent of the caller's stream locale.
template <class T>
void integer(std::ostream& output, T value) {
    if constexpr (std::is_enum_v<T>) {
        integer(output, static_cast<std::underlying_type_t<T>>(value));
    } else {
        std::array<char, 32> buffer{};
        const auto result = std::to_chars(buffer.data(), buffer.data() + buffer.size(), value);
        output.write(buffer.data(), result.ptr - buffer.data());
    }
}

template <class... T>
void record(std::ostream& output, const char* prefix, T... values) {
    output << prefix;
    ((output.put(' '), integer(output, values)), ...);
    output.put('\n');
}

std::ofstream open_output(const std::filesystem::path& path) {
    std::ofstream output(path);
    if (!output) throw std::runtime_error(path.string() + ": cannot open output");
    return output;
}

void finish(std::ofstream& output, const std::filesystem::path& path) {
    output.close();
    if (!output) throw std::runtime_error(path.string() + ": output write failed");
}

} // namespace

EngineConfig read_config(const std::filesystem::path& path) {
    Reader reader(path);
    reader.header("LLMATCH_CONFIG");
    if (!reader.next()) reader.fail("missing configuration record");
    reader.count(3);
    const EngineConfig config{
        reader.number<std::size_t>(0, "max_live_orders"),
        reader.number<Price>(1, "max_price"),
        reader.number<Quantity>(2, "max_order_qty")
    };
    if (reader.next()) reader.fail("unexpected additional configuration record");
    return config;
}

void write_config(const std::filesystem::path& path, const EngineConfig& config) {
    auto output = open_output(path);
    output << "LLMATCH_CONFIG 1\n";
    integer(output, config.max_live_orders);
    output.put(' ');
    integer(output, config.max_price);
    output.put(' ');
    integer(output, config.max_order_qty);
    output.put('\n');
    finish(output, path);
}

std::vector<Command> read_trace(const std::filesystem::path& path) {
    Reader reader(path);
    reader.header("LLMATCH_TRACE");
    std::vector<Command> commands;
    while (reader.next()) {
        const auto& type = reader.fields[0];
        if (type != "L" && type != "M" && type != "C") reader.fail("unknown command '" + type + "'");
        reader.count(type == "L" ? 7 : type == "M" ? 6 : 4);
        const auto client = reader.number<ClientId>(1, "client");
        const auto request = reader.number<RequestId>(2, "request");
        const auto id = reader.number<OrderId>(3, "order_id");
        if (type == "C") commands.push_back({client, request, CancelOrder{id}});
        else {
            const auto side = static_cast<Side>(reader.number<std::uint8_t>(4, "side"));
            if (type == "L") {
                const auto price = reader.number<Price>(5, "price");
                const auto quantity = reader.number<Quantity>(6, "quantity");
                commands.push_back({client, request, LimitOrder{id, side, price, quantity}});
            } else {
                commands.push_back({client, request, MarketOrder{id, side, reader.number<Quantity>(5, "quantity")}});
            }
        }
    }
    return commands;
}

void write_trace(const std::filesystem::path& path, std::span<const Command> commands) {
    auto output = open_output(path);
    output << "LLMATCH_TRACE 1\n";
    for (const auto& command : commands) {
        std::visit([&](const auto& order) {
            using T = std::decay_t<decltype(order)>;
            if constexpr (std::is_same_v<T, LimitOrder>) {
                record(output, "L", command.client, command.request, order.id, order.side, order.price, order.qty);
            } else if constexpr (std::is_same_v<T, MarketOrder>) {
                record(output, "M", command.client, command.request, order.id, order.side, order.qty);
            } else {
                record(output, "C", command.client, command.request, order.id);
            }
        }, command.payload);
    }
    finish(output, path);
}

void write_events(std::ostream& output, std::span<const Event> events) {
    for (const auto& event : events) {
        record(output, "E", event.kind, event.command_kind, event.command_seq, event.event_seq,
               event.client, event.request, event.order_id, event.reject_reason, event.cancel_reason,
               event.completion, event.side, event.price, event.qty, event.arrival_seq,
               event.maker_id, event.taker_id, event.maker_client, event.taker_client,
               event.maker_arrival_seq, event.taker_arrival_seq,
               event.filled_qty, event.resting_qty, event.cancelled_qty);
    }
    if (!output) throw std::runtime_error("event output write failed");
}

void write_snapshot(std::ostream& output, const BookSnapshot& snapshot) {
    output << "BOOK 1\n";
    const auto levels = [&](const char* side, const std::vector<LevelSnapshot>& data) {
        for (const auto& level : data) {
            record(output, side, level.price, level.total_qty, level.orders.size());
            for (const auto& order : level.orders) {
                record(output, "O", order.id, order.owner, order.side, order.price, order.remaining, order.arrival_seq);
            }
        }
    };
    levels("B", snapshot.bids);
    levels("A", snapshot.asks);
    if (!output) throw std::runtime_error("snapshot output write failed");
}

std::string file_hash(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error(path.string() + ": cannot open hash input");
    std::uint64_t hash = 14695981039346656037ULL;
    std::array<char, 8192> buffer{};
    while (input.read(buffer.data(), static_cast<std::streamsize>(buffer.size())) || input.gcount() != 0) {
        for (std::streamsize i = 0; i < input.gcount(); ++i) {
            hash ^= static_cast<unsigned char>(buffer[static_cast<std::size_t>(i)]);
            hash *= 1099511628211ULL;
        }
    }
    if (input.bad()) throw std::runtime_error(path.string() + ": hash input read failed");
    std::ostringstream result;
    result.imbue(std::locale::classic());
    result << "fnv1a64:" << std::hex << std::setfill('0') << std::setw(16) << hash;
    return result.str();
}

} // namespace llmatch::trace
