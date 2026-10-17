#include "llmatch/itch.hpp"

#include <algorithm>
#include <charconv>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <set>
#include <string>

namespace {
using namespace llmatch::itch;

void quoted(std::ostream& out, const std::string& value) {
    constexpr char hex[] = "0123456789abcdef";
    out << '"';
    for (const char character : value) {
        const auto c = static_cast<unsigned char>(character);
        if (c == '"' || c == '\\') out << '\\' << static_cast<char>(c);
        else if (c < 32) out << "\\u00" << hex[c >> 4U] << hex[c & 15U];
        else out << static_cast<char>(c);
    }
    out << '"';
}

void order_json(std::ostream& out, const Order& order) {
    out << "{\"reference\":" << order.reference << ",\"side\":\"" << order.side
        << "\",\"price\":" << order.price << ",\"shares\":" << order.shares << ",\"attribution\":";
    quoted(out, order.attribution);
    out << '}';
}

void level_json(std::ostream& out, const Level& level) {
    out << "{\"side\":\"" << level.side << "\",\"price\":" << level.price
        << ",\"shares\":" << level.shares << ",\"orders\":" << level.orders << '}';
}

void bbo_json(std::ostream& out, const Bbo& bbo) {
    out << "{\"bid\":";
    if (bbo.bid) level_json(out, *bbo.bid); else out << "null";
    out << ",\"ask\":";
    if (bbo.ask) level_json(out, *bbo.ask); else out << "null";
    out << '}';
}

template <class T, class Writer>
void array_json(std::ostream& out, const std::vector<T>& items, Writer writer) {
    out << '[';
    bool first = true;
    for (const auto& item : items) {
        if (!first) out << ',';
        first = false;
        writer(out, item);
    }
    out << ']';
}

void counts_json(std::ostream& out, const std::map<char, std::uint64_t>& counts) {
    out << '{';
    bool first = true;
    for (const auto& [type, count] : counts) {
        if (!first) out << ',';
        first = false;
        quoted(out, std::string(1, type));
        out << ':' << count;
    }
    out << '}';
}

void summary_json(std::ostream& out, const BinaryFileReader& reader, const Reconstructor& book, bool prefix) {
    const auto& s = book.statistics();
    out << std::boolalpha << "{\"schema_version\":1,\"status\":\"passed\",\"symbol\":";
    quoted(out, book.symbol());
    out << ",\"stock_locate\":" << *book.stock_locate() << ",\"prefix_allowed\":" << prefix
        << ",\"session_complete\":" << (reader.ended() && book.itch_end())
        << ",\"binary_end\":" << reader.ended() << ",\"itch_end\":" << book.itch_end()
        << ",\"bytes\":" << reader.bytes() << ",\"last_offset\":" << reader.last_offset()
        << ",\"messages\":" << s.messages << ",\"target_messages\":" << s.target_messages
        << ",\"updates\":" << s.updates << ",\"filtered_messages\":" << s.filtered_messages
        << ",\"counts_by_type\":";
    counts_json(out, s.counts_by_type);
    out << ",\"ignored_by_type\":";
    counts_json(out, s.ignored_by_type);
    out << ",\"system_events\":";
    quoted(out, s.system_events);
    out << ",\"active_orders\":" << book.size() << ",\"bbo\":";
    bbo_json(out, book.bbo());
    out << ",\"input_fnv1a64\":\"" << reader.input_hash() << "\"}";
}

void snapshot_json(std::ostream& out, const Reconstructor& book) {
    out << "\"orders\":";
    array_json(out, book.orders(), order_json);
    out << ",\"levels\":";
    array_json(out, book.levels(), level_json);
}

bool canonical_level(const Level& a, const Level& b) {
    if (a.side != b.side) return a.side == 'B';
    return a.side == 'B' ? a.price > b.price : a.price < b.price;
}

void audit_update(std::ostream& out, const Message& message, const std::optional<Order>& before,
                  const Reconstructor& book) {
    std::vector<std::uint64_t> refs{message.reference};
    if (message.type == 'U') refs.push_back(message.new_reference);
    std::sort(refs.begin(), refs.end());
    refs.erase(std::unique(refs.begin(), refs.end()), refs.end());
    std::vector<Level> affected;
    if (before) affected.push_back(book.level(before->side, before->price));
    for (const auto reference : refs) {
        if (const auto* order = book.find(reference)) affected.push_back(book.level(order->side, order->price));
    }
    std::sort(affected.begin(), affected.end(), canonical_level);
    affected.erase(std::unique(affected.begin(), affected.end()), affected.end());
    out << "{\"kind\":\"update\",\"message_index\":" << message.message_index << ",\"offset\":" << message.offset
        << ",\"type\":\"" << message.type << "\",\"update_index\":" << book.statistics().updates << ",\"orders\":[";
    bool first = true;
    for (const auto reference : refs) {
        if (!first) out << ',';
        first = false;
        out << "{\"reference\":" << reference << ",\"state\":";
        if (const auto* order = book.find(reference)) order_json(out, *order); else out << "null";
        out << '}';
    }
    out << "],\"levels\":";
    array_json(out, affected, level_json);
    out << ",\"bbo\":";
    bbo_json(out, book.bbo());
    out << ",\"active_orders\":" << book.size() << "}\n";
}

std::size_t positive(const std::string& value, const std::string& option) {
    std::size_t result{};
    const auto parsed = std::from_chars(value.data(), value.data() + value.size(), result);
    if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size() || result == 0)
        throw std::invalid_argument(option + " requires a positive integer");
    return result;
}

std::ofstream output(const std::filesystem::path& path) {
    std::ofstream stream;
    stream.exceptions(std::ios::failbit | std::ios::badbit);
    stream.open(path);
    return stream;
}

std::string csv_text(const std::string& value) {
    if (value.find_first_of(",\"\r\n") == std::string::npos) return value;
    std::string result = "\"";
    for (const char c : value) { if (c == '"') result += '"'; result += c; }
    return result + '"';
}
} // namespace

int main(int argc, char** argv) {
    std::filesystem::path input_path, directory;
    bool prepared_directory = false;
    try {
        std::string symbol;
        bool prefix = false, audit = false;
        std::size_t maximum_orders = 1'000'000, checkpoint_every = 10'000, chunk_size = 65'536;
        std::set<std::string> seen;
        for (int i = 1; i < argc; ++i) {
            const std::string option = argv[i];
            if (!seen.insert(option).second) throw std::invalid_argument("duplicate option " + option);
            if (option == "--prefix") prefix = true;
            else if (option == "--audit-stdout") audit = true;
            else {
                if (i + 1 == argc) throw std::invalid_argument("missing value for " + option);
                const std::string value = argv[++i];
                if (option == "--input") input_path = value;
                else if (option == "--symbol") symbol = value;
                else if (option == "--output-dir") directory = value;
                else if (option == "--max-orders") maximum_orders = positive(value, option);
                else if (option == "--checkpoint-every") checkpoint_every = positive(value, option);
                else if (option == "--read-chunk-size") chunk_size = positive(value, option);
                else throw std::invalid_argument("unknown option " + option);
            }
        }
        if (input_path.empty() || symbol.empty() || directory.empty())
            throw std::invalid_argument("usage: itch_replay --input FILE --symbol SYMBOL --output-dir DIR [--prefix] [--max-orders N] [--audit-stdout] [--checkpoint-every N] [--read-chunk-size N]");
        if (chunk_size > static_cast<std::size_t>(std::numeric_limits<std::streamsize>::max()))
            throw std::invalid_argument("read chunk size exceeds stream limit");
        for (const auto* name : {"summary.json", "orders.csv", "levels.csv", "error.json"}) {
            if (std::filesystem::exists(directory / name)) throw std::invalid_argument("output already exists: " + (directory / name).string());
        }
        std::filesystem::create_directories(directory);
        prepared_directory = true;
        std::ifstream input(input_path, std::ios::binary);
        if (!input) throw std::runtime_error("cannot open input " + input_path.string());
        Reconstructor book(symbol, maximum_orders);
        BinaryFileReader reader;
        std::cout.exceptions(std::ios::failbit | std::ios::badbit);
        const auto handle = [&](const Message& message) {
            std::optional<Order> before;
            if (audit && book.stock_locate() && message.stock_locate == *book.stock_locate()) {
                if (const auto* order = book.find(message.reference)) before = *order;
            }
            if (book.apply(message) && audit) {
                audit_update(std::cout, message, before, book);
                if (book.statistics().updates % checkpoint_every == 0) {
                    std::cout << "{\"kind\":\"checkpoint\",\"message_index\":" << message.message_index
                              << ",\"update_index\":" << book.statistics().updates << ',';
                    snapshot_json(std::cout, book);
                    std::cout << "}\n";
                }
            }
        };
        std::vector<std::uint8_t> buffer(chunk_size);
        while (input) {
            input.read(reinterpret_cast<char*>(buffer.data()), static_cast<std::streamsize>(buffer.size()));
            const auto size = input.gcount();
            if (size > 0) reader.feed(std::span(buffer).first(static_cast<std::size_t>(size)), handle);
        }
        if (input.bad() || (!input.eof() && input.fail())) throw std::runtime_error("input read failed");
        reader.finish();
        book.finish(reader.ended(), prefix);
        if (audit) book.check_invariants();
        {
            auto stream = output(directory / "orders.csv");
            stream << "reference,side,price,shares,attribution\n";
            for (const auto& order : book.orders()) stream << order.reference << ',' << order.side << ',' << order.price
                << ',' << order.shares << ',' << csv_text(order.attribution) << '\n';
            stream.close();
        }
        {
            auto stream = output(directory / "levels.csv");
            stream << "side,price,shares,orders\n";
            for (const auto& level : book.levels()) stream << level.side << ',' << level.price << ',' << level.shares << ',' << level.orders << '\n';
            stream.close();
        }
        {
            auto stream = output(directory / "summary.json");
            summary_json(stream, reader, book, prefix);
            stream << '\n';
            stream.close();
        }
        if (audit) {
            std::cout << "{\"kind\":\"final\",\"summary\":";
            summary_json(std::cout, reader, book, prefix);
            std::cout << ',';
            snapshot_json(std::cout, book);
            std::cout << "}\n";
            std::cout.flush();
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "itch_replay: " << error.what() << '\n';
        if (prepared_directory) {
            try {
                auto stream = output(directory / "error.json");
                stream << "{\"schema_version\":1,\"status\":\"failed\",\"error\":";
                quoted(stream, error.what());
                if (const auto* contextual = dynamic_cast<const Error*>(&error)) {
                    stream << ",\"offset\":" << contextual->offset << ",\"message_index\":" << contextual->message_index << ",\"type\":";
                    quoted(stream, contextual->type_label());
                    if (contextual->reference) stream << ",\"reference\":" << *contextual->reference;
                }
                stream << "}\n";
                stream.close();
            } catch (const std::exception& output_error) {
                std::cerr << "itch_replay: cannot save error receipt: " << output_error.what() << '\n';
            }
        }
        return 1;
    }
}
