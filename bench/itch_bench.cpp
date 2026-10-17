#include "llmatch/itch.hpp"

#include <charconv>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <string_view>
#include <sys/resource.h>

namespace {
using namespace llmatch::itch;
using Clock = std::chrono::steady_clock;
constexpr std::uint64_t basis = 14695981039346656037ULL;
constexpr std::uint64_t prime = 1099511628211ULL;

struct Options {
    std::filesystem::path input, output;
    std::string symbol, mode;
    std::size_t max_orders = 1'000'000;
    bool prefix = false;
};

Options options(int argc, char** argv) {
    Options result;
    for (int i = 1; i < argc; ++i) {
        const std::string key = argv[i];
        if (key == "--prefix") { result.prefix = true; continue; }
        if (i + 1 == argc) throw std::runtime_error("missing value for " + key);
        const std::string value = argv[++i];
        if (key == "--input") result.input = value;
        else if (key == "--output") result.output = value;
        else if (key == "--symbol") result.symbol = value;
        else if (key == "--mode") result.mode = value;
        else if (key == "--max-orders") {
            const auto parsed = std::from_chars(value.data(), value.data() + value.size(), result.max_orders);
            if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size() || result.max_orders == 0)
                throw std::runtime_error("max-orders must be positive");
        } else throw std::runtime_error("unknown option " + key);
    }
    if (result.input.empty() || result.output.empty() || result.symbol.empty() ||
        (result.mode != "decode" && result.mode != "rebuild"))
        throw std::runtime_error("usage: bench_itch --input FILE --symbol SYMBOL --mode decode|rebuild --output FILE [--prefix] [--max-orders N]");
    if (std::filesystem::exists(result.output)) throw std::runtime_error("output already exists");
    return result;
}

std::uint64_t elapsed(Clock::time_point start, Clock::time_point end) {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count());
}

rusage usage() {
    rusage value{};
    if (getrusage(RUSAGE_SELF, &value) != 0) throw std::runtime_error("getrusage failed");
    return value;
}

std::uint64_t micros(timeval value) {
    return static_cast<std::uint64_t>(value.tv_sec) * 1'000'000 + static_cast<std::uint64_t>(value.tv_usec);
}

std::uint64_t rss(const rusage& value) {
#ifdef __APPLE__
    return static_cast<std::uint64_t>(value.ru_maxrss);
#else
    return static_cast<std::uint64_t>(value.ru_maxrss) * 1024;
#endif
}

void mix(std::uint64_t& hash, std::uint64_t value) { hash = (hash ^ value) * prime; }
void mix(std::uint64_t& hash, const std::string& value) {
    for (const char byte : value) mix(hash, static_cast<unsigned char>(byte));
    mix(hash, 0);
}
void consume(std::uint64_t& hash, const Message& message) {
    mix(hash, static_cast<unsigned char>(message.type));
    mix(hash, message.stock_locate); mix(hash, message.tracking_number); mix(hash, message.timestamp);
    mix(hash, message.offset); mix(hash, message.message_index); mix(hash, message.reference);
    mix(hash, message.new_reference); mix(hash, message.match_number); mix(hash, message.shares); mix(hash, message.price);
    mix(hash, static_cast<unsigned char>(message.side)); mix(hash, static_cast<unsigned char>(message.event));
    mix(hash, static_cast<unsigned char>(message.printable)); mix(hash, message.symbol);
    mix(hash, message.attribution); mix(hash, message.ignored);
}

std::string hex(std::uint64_t value) {
    std::ostringstream out;
    out << std::hex << std::setfill('0') << std::setw(16) << value;
    return out.str();
}
} // namespace

int main(int argc, char** argv) {
    try {
        const auto opts = options(argc, argv);
        // Input I/O, empty-book/handler construction and clock observation are outside the interval.
        std::uint64_t min_tick = 0, zero_ticks = 0;
        for (int i = 0; i < 10'000; ++i) {
            const auto before = Clock::now();
            const auto tick = elapsed(before, Clock::now());
            if (tick == 0) ++zero_ticks;
            else if (min_tick == 0 || tick < min_tick) min_tick = tick;
        }
        const auto read_start = Clock::now();
        std::ifstream input(opts.input, std::ios::binary | std::ios::ate);
        if (!input || input.tellg() < 0) throw std::runtime_error("cannot open input");
        std::vector<std::uint8_t> bytes(static_cast<std::size_t>(input.tellg()));
        input.seekg(0);
        input.read(reinterpret_cast<char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
        if (!input) throw std::runtime_error("input read failed");
        input.close();
        const auto read_ns = elapsed(read_start, Clock::now());
        const auto input_rss = rss(usage());
        const auto construct_start = Clock::now();
        BinaryFileReader reader;
        std::unique_ptr<Reconstructor> book;
        if (opts.mode == "rebuild") book = std::make_unique<Reconstructor>(opts.symbol, opts.max_orders);
        std::uint64_t decoded_checksum = basis, target_messages = 0, target_updates = 0;
        std::optional<std::uint16_t> target_locate;
        bool session_started = false, session_ended = false;
        const BinaryFileReader::Handler handler = [&](const Message& message) {
            if (!book) {
                if (session_ended) throw std::runtime_error("payload after ITCH End of Messages");
                if (!session_started && (message.type != 'S' || message.event != 'O'))
                    throw std::runtime_error("first payload must be S/O");
                if (message.type == 'S') {
                    if (message.event == 'O' && session_started) throw std::runtime_error("duplicate session start");
                    session_started = true;
                    session_ended = message.event == 'C';
                }
            }
            consume(decoded_checksum, message);
            if (message.type == 'R' && message.symbol == opts.symbol) target_locate = message.stock_locate;
            if (message.type != 'S' && target_locate && message.stock_locate == *target_locate) {
                ++target_messages;
                if (std::string_view("AFECXDU").find(message.type) != std::string_view::npos) ++target_updates;
            }
            if (book) (void)book->apply(message);
        };
        const auto construct_ns = elapsed(construct_start, Clock::now());
        const auto construct_rss = rss(usage());
        const auto cpu_before = usage();
        const auto started = Clock::now();
        reader.feed(bytes, handler);
        const auto stopped = Clock::now();
        const auto cpu_after = usage();

        const auto finish_start = Clock::now();
        reader.finish();
        if (book) book->finish(reader.ended(), opts.prefix);
        else if (!session_started || (!opts.prefix && (!reader.ended() || !session_ended)) ||
                 (reader.ended() && !session_ended))
            throw std::runtime_error("incomplete session (requires S/C and BinaryFILE end)");
        if (!target_locate || target_updates == 0) throw std::runtime_error("no target updates in benchmark input");
        const auto finish_ns = elapsed(finish_start, Clock::now());
        const auto snapshot_start = Clock::now();
        std::uint64_t state_checksum = basis;
        std::size_t active_orders = 0, level_count = 0;
        if (book) {
            const auto orders = book->orders();
            const auto levels = book->levels();
            active_orders = orders.size(); level_count = levels.size();
            mix(state_checksum, active_orders);
            for (const auto& order : orders) {
                mix(state_checksum, order.reference); mix(state_checksum, static_cast<unsigned char>(order.side));
                mix(state_checksum, order.price); mix(state_checksum, order.shares); mix(state_checksum, order.attribution);
            }
            mix(state_checksum, level_count);
            for (const auto& level : levels) {
                mix(state_checksum, static_cast<unsigned char>(level.side)); mix(state_checksum, level.price);
                mix(state_checksum, level.shares); mix(state_checksum, level.orders);
            }
            if (book->statistics().updates != target_updates || book->statistics().target_messages != target_messages)
                throw std::runtime_error("benchmark target counts disagree with reconstruction");
        }
        const auto snapshot_ns = elapsed(snapshot_start, Clock::now());
        const auto final_rss = rss(usage());
        const auto duration = elapsed(started, stopped);
        if (duration == 0) throw std::runtime_error("clock did not resolve the timing interval");
        const auto write_start = Clock::now();
        std::ofstream output(opts.output);
        if (!output) throw std::runtime_error("cannot open benchmark output");
        output << "{\"schema_version\":1,\"status\":\"passed\",\"mode\":" << std::quoted(opts.mode)
               << ",\"symbol\":" << std::quoted(opts.symbol) << ",\"prefix_allowed\":" << (opts.prefix ? "true" : "false")
               << ",\"traversals\":1,\"bytes\":" << reader.bytes() << ",\"messages\":" << reader.messages()
               << ",\"target_messages\":" << target_messages << ",\"target_updates\":" << target_updates
               << ",\"input_fnv1a64\":" << std::quoted(reader.input_hash())
               << ",\"decoded_checksum\":" << std::quoted(hex(decoded_checksum))
               << ",\"elapsed_ns\":" << duration << ",\"cpu_user_us\":" << micros(cpu_after.ru_utime) - micros(cpu_before.ru_utime)
               << ",\"cpu_system_us\":" << micros(cpu_after.ru_stime) - micros(cpu_before.ru_stime)
               << ",\"input_read_ns\":" << read_ns << ",\"construction_ns\":" << construct_ns
               << ",\"finish_ns\":" << finish_ns << ",\"final_snapshot_ns\":" << snapshot_ns
               << ",\"input_storage_bytes\":" << bytes.capacity()
               << ",\"rss_after_input_bytes\":" << input_rss << ",\"rss_after_construction_bytes\":" << construct_rss
               << ",\"peak_rss_after_timing_bytes\":" << rss(cpu_after) << ",\"peak_rss_after_snapshot_bytes\":" << final_rss
               << ",\"active_orders\":" << (book ? std::to_string(active_orders) : "null")
               << ",\"levels\":" << (book ? std::to_string(level_count) : "null")
               << ",\"state_checksum\":" << (book ? '"' + hex(state_checksum) + '"' : "null")
               << ",\"clock\":{\"steady\":" << (Clock::is_steady ? "true" : "false")
               << ",\"period_num\":" << Clock::period::num << ",\"period_den\":" << Clock::period::den
               << ",\"probe_pairs\":10000,\"zero_intervals\":" << zero_ticks << ",\"minimum_positive_ns\":" << min_tick << "}}\n";
        output.close();
        if (!output) throw std::runtime_error("benchmark output write failed");
        std::cout << "{\"status\":\"passed\",\"output_write_ns\":" << elapsed(write_start, Clock::now()) << "}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "bench_itch: " << error.what() << '\n';
        return 1;
    }
}
