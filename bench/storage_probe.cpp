#include "llmatch/matching_engine.hpp"
#include "reference_engine.hpp"
#include "trace_io.hpp"

#include <algorithm>
#include <array>
#include <charconv>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <new>
#include <optional>
#include <stdexcept>
#include <sys/resource.h>
#include <unistd.h>
#include <vector>
#ifdef __APPLE__
#include <mach/mach.h>
#endif

// These replacements belong only to this single-threaded diagnostic executable.
// A header remembers requested bytes, including for unsized delete. Its allocator
// overhead is deliberately excluded from requested-byte counts, not from RSS or
// timings. Ordinary benchmark and production executables never link this file.
namespace allocation_probe {
struct Counts {
    std::uint64_t allocations{}, frees{}, allocated_bytes{}, freed_bytes{};
};
struct Header {
    void* base;
    std::size_t bytes;
    bool tracked;
};
Counts* active{};
std::uint64_t live_bytes{}, live_blocks{};

void* allocate(std::size_t bytes, std::size_t alignment) {
    const auto payload = std::max<std::size_t>(bytes, 1);
    const auto overhead = sizeof(Header) + alignment - 1;
    if (payload > std::numeric_limits<std::size_t>::max() - overhead) throw std::bad_alloc();
    void* base = std::malloc(payload + overhead);
    if (!base) throw std::bad_alloc();
    const auto start = reinterpret_cast<std::uintptr_t>(base) + sizeof(Header);
    const auto address = (start + alignment - 1) & ~(alignment - 1);
    auto* header = reinterpret_cast<Header*>(address) - 1;
    *header = {base, bytes, active != nullptr};
    if (active) {
        ++active->allocations;
        active->allocated_bytes += bytes;
        ++live_blocks;
        live_bytes += bytes;
    }
    return reinterpret_cast<void*>(address);
}

void release(void* pointer) noexcept {
    if (!pointer) return;
    const auto* header = static_cast<Header*>(pointer) - 1;
    if (header->tracked) {
        --live_blocks;
        live_bytes -= header->bytes;
        if (active) {
            ++active->frees;
            active->freed_bytes += header->bytes;
        }
    }
    std::free(header->base);
}

struct Scope {
    explicit Scope(Counts& counts) { active = &counts; }
    ~Scope() { active = nullptr; }
};
}

void* operator new(std::size_t bytes) {
    return allocation_probe::allocate(bytes, alignof(std::max_align_t));
}
void* operator new[](std::size_t bytes) { return ::operator new(bytes); }
void* operator new(std::size_t bytes, std::align_val_t alignment) {
    return allocation_probe::allocate(bytes, static_cast<std::size_t>(alignment));
}
void* operator new[](std::size_t bytes, std::align_val_t alignment) { return ::operator new(bytes, alignment); }
void operator delete(void* pointer) noexcept { allocation_probe::release(pointer); }
void operator delete[](void* pointer) noexcept { allocation_probe::release(pointer); }
void operator delete(void* pointer, std::size_t) noexcept { allocation_probe::release(pointer); }
void operator delete[](void* pointer, std::size_t) noexcept { allocation_probe::release(pointer); }
void operator delete(void* pointer, std::align_val_t) noexcept { allocation_probe::release(pointer); }
void operator delete[](void* pointer, std::align_val_t) noexcept { allocation_probe::release(pointer); }
void operator delete(void* pointer, std::size_t, std::align_val_t) noexcept { allocation_probe::release(pointer); }
void operator delete[](void* pointer, std::size_t, std::align_val_t) noexcept { allocation_probe::release(pointer); }

namespace {
using namespace llmatch;
using Clock = std::chrono::steady_clock;
using Counts = allocation_probe::Counts;
struct Options {
    std::filesystem::path config, setup, input, output;
    std::size_t max_commands{2000}, construction_repeats{100};
};

std::size_t positive(const std::string& value) {
    std::size_t number{};
    const auto parsed = std::from_chars(value.data(), value.data() + value.size(), number);
    if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size() || number == 0) {
        throw std::runtime_error("count must be a positive integer");
    }
    return number;
}

Options options(int argc, char** argv) {
    Options result;
    for (int i = 1; i < argc; ++i) {
        const std::string key = argv[i];
        if (i + 1 == argc) throw std::runtime_error("missing value for " + key);
        const std::string value = argv[++i];
        if (key == "--config") result.config = value;
        else if (key == "--setup") result.setup = value;
        else if (key == "--input") result.input = value;
        else if (key == "--output") result.output = value;
        else if (key == "--max-commands") result.max_commands = positive(value);
        else if (key == "--construction-repeats") result.construction_repeats = positive(value);
        else throw std::runtime_error("unknown option " + key);
    }
    if (result.config.empty() || result.setup.empty() || result.input.empty() || result.output.empty()) {
        throw std::runtime_error("usage: storage_probe --config FILE --setup FILE --input FILE --output FILE "
                                 "[--max-commands 2000] [--construction-repeats 100]");
    }
    return result;
}

struct Memory {
    std::uint64_t engine_requested_bytes{}, engine_allocations{}, rss_bytes{}, max_rss_bytes{};
    std::size_t live_orders{};
};

Memory memory(std::size_t live_orders) {
    Memory result{allocation_probe::live_bytes, allocation_probe::live_blocks, 0, 0, live_orders};
    rusage usage{};
    if (getrusage(RUSAGE_SELF, &usage) != 0) throw std::runtime_error("getrusage failed");
#ifdef __APPLE__
    result.max_rss_bytes = static_cast<std::uint64_t>(usage.ru_maxrss);
    mach_task_basic_info info{};
    mach_msg_type_number_t count = MACH_TASK_BASIC_INFO_COUNT;
    if (task_info(mach_task_self(), MACH_TASK_BASIC_INFO, reinterpret_cast<task_info_t>(&info), &count) != KERN_SUCCESS) {
        throw std::runtime_error("task_info failed");
    }
    result.rss_bytes = info.resident_size;
#else
    result.max_rss_bytes = static_cast<std::uint64_t>(usage.ru_maxrss) * 1024;
    auto* statm = std::fopen("/proc/self/statm", "r");
    if (!statm) throw std::runtime_error("cannot read /proc/self/statm");
    unsigned long total{}, resident{};
    const int fields = std::fscanf(statm, "%lu %lu", &total, &resident);
    std::fclose(statm);
    const long page_size = sysconf(_SC_PAGESIZE);
    if (fields != 2 || page_size <= 0) throw std::runtime_error("invalid resident memory reading");
    result.rss_bytes = resident * static_cast<std::uint64_t>(page_size);
#endif
    return result;
}

std::size_t live_count(const BookSnapshot& book) {
    std::size_t count{};
    for (const auto& level : book.bids) count += level.orders.size();
    for (const auto& level : book.asks) count += level.orders.size();
    return count;
}

struct CommandCounts {
    Counts allocation;
    std::size_t commands{}, accepted{}, rejected{}, rested{}, trades{}, user_cancels{}, ioc_remainders{};
};
using Groups = std::array<CommandCounts, 3>;

void consume(CommandCounts& counts, std::span<const Event> events) {
    ++counts.commands;
    for (const auto& event : events) {
        switch (event.kind) {
        case EventKind::Accepted: ++counts.accepted; break;
        case EventKind::Rejected: ++counts.rejected; break;
        case EventKind::Rested: ++counts.rested; break;
        case EventKind::Trade: ++counts.trades; break;
        case EventKind::Cancelled:
            if (event.cancel_reason == CancelReason::UserCancel) ++counts.user_cancels;
            else ++counts.ioc_remainders;
            break;
        case EventKind::CommandComplete: break;
        }
    }
}

void commands(MatchingEngine& engine, ReferenceEngine& reference, std::span<const Command> input,
              std::vector<Event>& actual, std::vector<Event>& expected, Groups& groups,
              Memory& peak, std::size_t& minimum_live) {
    for (const auto& command : input) {
        auto& group = groups[static_cast<std::size_t>(command_kind(command))];
        ProcessResult result{};
        {
            allocation_probe::Scope scope(group.allocation);
            result = engine.process(command, actual);
        }
        const auto wanted = reference.process(command, expected);
        if (result.status != ProcessStatus::Processed || result != wanted ||
            !std::equal(actual.begin(), actual.begin() + static_cast<std::ptrdiff_t>(result.event_count), expected.begin())) {
            throw std::runtime_error("Reference event mismatch at request " + std::to_string(command.request));
        }
        consume(group, std::span<const Event>(actual.data(), result.event_count));
        engine.check_invariants();
        const auto snapshot = engine.snapshot();
        if (snapshot != reference.snapshot()) throw std::runtime_error("Reference state mismatch");
        const auto live = live_count(snapshot);
        minimum_live = std::min(minimum_live, live);
        if (live > peak.live_orders) peak = memory(live);
    }
}

void counts_json(std::ostream& out, const Counts& value) {
    out << "\"allocations\":" << value.allocations << ",\"frees\":" << value.frees
        << ",\"allocated_requested_bytes\":" << value.allocated_bytes
        << ",\"freed_requested_bytes\":" << value.freed_bytes;
}

void memory_json(std::ostream& out, const Memory& value) {
    out << "{\"live_orders\":" << value.live_orders
        << ",\"engine_live_requested_bytes\":" << value.engine_requested_bytes
        << ",\"engine_live_allocations\":" << value.engine_allocations
        << ",\"process_rss_bytes\":" << value.rss_bytes
        << ",\"process_high_water_rss_bytes\":" << value.max_rss_bytes << '}';
}

void groups_json(std::ostream& out, const Groups& groups) {
    constexpr std::array names{"limit", "market", "cancel"};
    out << '{';
    for (std::size_t i = 0; i < groups.size(); ++i) {
        if (i) out << ',';
        const auto& group = groups[i];
        out << '"' << names[i] << "\":{";
        counts_json(out, group.allocation);
        out << ",\"commands\":" << group.commands << ",\"accepted\":" << group.accepted
            << ",\"rejected\":" << group.rejected << ",\"rested\":" << group.rested
            << ",\"trades\":" << group.trades << ",\"user_cancels\":" << group.user_cancels
            << ",\"ioc_remainders\":" << group.ioc_remainders << '}';
    }
    out << '}';
}

int run(int argc, char** argv) {
    const auto opts = options(argc, argv);
    if (std::filesystem::exists(opts.output)) throw std::runtime_error("refusing to overwrite an existing diagnostic");
    const auto config = trace::read_config(opts.config);
    const auto setup = trace::read_trace(opts.setup);
    const auto input = trace::read_trace(opts.input);
    const auto measured = std::span(input).first(std::min(input.size(), opts.max_commands));
    if (measured.empty()) throw std::runtime_error("diagnostic input is empty");
    const auto config_hash = trace::file_hash(opts.config), setup_hash = trace::file_hash(opts.setup), input_hash = trace::file_hash(opts.input);

    // Bounded constructor observations. Parsing, Reference, destructor and output
    // are outside each interval; replacement-allocator header overhead remains.
    std::vector<std::uint64_t> construction_ns(opts.construction_repeats);
    for (auto& ns : construction_ns) {
        std::optional<OrderBook> book;
        const auto begin = Clock::now();
        book.emplace(config.max_live_orders);
        const auto end = Clock::now();
        ns = static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(end - begin).count());
    }
    std::vector<Event> actual(config.max_live_orders + 4), expected(config.max_live_orders + 4);
    ReferenceEngine reference(config);
    std::optional<MatchingEngine> engine;
    Counts construction, destruction;
    {
        allocation_probe::Scope scope(construction);
        engine.emplace(config);
    }
    const auto empty = memory(0);
    Memory peak = empty;
    std::size_t setup_minimum_live = 0;
    Groups setup_groups{}, measured_groups{};
    commands(*engine, reference, setup, actual, expected, setup_groups, peak, setup_minimum_live);
    const auto after_setup = memory(live_count(engine->snapshot()));
    std::size_t measured_minimum_live = after_setup.live_orders;
    Memory measured_peak = after_setup;
    commands(*engine, reference, measured, actual, expected, measured_groups, measured_peak, measured_minimum_live);
    if (measured_peak.live_orders > peak.live_orders) peak = measured_peak;
    const auto final = memory(live_count(engine->snapshot()));
    {
        allocation_probe::Scope scope(destruction);
        engine.reset();
    }
    if (allocation_probe::live_blocks || allocation_probe::live_bytes) throw std::runtime_error("engine allocations remain after destruction");
    if (trace::file_hash(opts.config) != config_hash || trace::file_hash(opts.setup) != setup_hash || trace::file_hash(opts.input) != input_hash) {
        throw std::runtime_error("diagnostic input changed during execution");
    }

    std::ofstream out(opts.output);
    if (!out) throw std::runtime_error("cannot write diagnostic output");
    out << "{\n\"schema_version\":1,\"diagnostic_only\":true,\"reference_passed\":true,"
        << "\n\"counter_scope\":\"Global C++ new/delete in this executable, enabled only around MatchingEngine constructor, process and destructor. Includes price-map and OrderId hash nodes and buckets. Excludes parsing, Reference, event sinks, snapshots, invariant scans, output and libc allocations. Freed bytes count the original requested bytes of tracked allocations.\","
        << "\n\"memory_scope\":\"Requested bytes exclude allocator metadata, alignment padding and diagnostic headers; they are not malloc physical occupancy or process RSS. Engine object is stack resident. RSS covers the entire diagnostic including parsed full input, Reference, snapshots and constructor observations; high-water RSS is not current RSS.\","
        << "\n\"initialization_scope\":\"OrderBook constructor only, counters disabled, each fresh object destroyed outside interval. The diagnostic replacement allocator still adds its header and alignment overhead. Includes bucket reservation and candidate slots; does not isolate slot-only time and is not a production startup benchmark. All raw observations retained; no clock-overhead subtraction.\","
        << "\n\"hash_algorithm\":\"fnv1a64\",\"config_hash\":\"" << config_hash
        << "\",\"setup_hash\":\"" << setup_hash << "\",\"input_hash\":\"" << input_hash << "\","
        << "\n\"capacity\":" << config.max_live_orders << ",\"input_commands\":" << input.size()
        << ",\"measured_prefix_commands\":" << measured.size() << ",\"setup_commands\":" << setup.size()
        << ",\"sizeof_order\":" << sizeof(Order) << ",\"sizeof_order_book\":" << sizeof(OrderBook)
        << ",\"sizeof_matching_engine\":" << sizeof(MatchingEngine)
        << ",\"diagnostic_header_bytes\":" << sizeof(allocation_probe::Header)
        << ",\"construction_repeats\":" << opts.construction_repeats << ",\"order_book_construction_ns\":[";
    for (std::size_t i = 0; i < construction_ns.size(); ++i) {
        if (i) out << ',';
        out << construction_ns[i];
    }
    out << "],\n\"construction\":{"; counts_json(out, construction);
    out << "},\"setup\":"; groups_json(out, setup_groups);
    out << ",\"measured\":"; groups_json(out, measured_groups);
    out << ",\"destruction\":{"; counts_json(out, destruction);
    out << "},\n\"empty\":"; memory_json(out, empty);
    out << ",\"after_setup\":"; memory_json(out, after_setup);
    out << ",\"peak_live_orders_observation\":"; memory_json(out, peak);
    out << ",\"final\":"; memory_json(out, final);
    out << ",\"measured_min_live_orders\":" << measured_minimum_live
        << ",\"measured_max_live_orders\":" << measured_peak.live_orders
        << ",\"engine_live_requested_bytes_after_destruction\":0,\"engine_live_allocations_after_destruction\":0\n}\n";
    out.close();
    if (!out) throw std::runtime_error("diagnostic output write failed");
    std::cout << "verified " << measured.size() << " diagnostic commands; " << opts.output << '\n';
    return 0;
}
}

int main(int argc, char** argv) {
    try { return run(argc, argv); }
    catch (const std::exception& error) {
        allocation_probe::active = nullptr;
        std::cerr << "storage_probe: " << error.what() << '\n';
        return 1;
    }
}
