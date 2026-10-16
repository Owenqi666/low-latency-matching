#include "llmatch/matching_engine.hpp"
#include "reference_engine.hpp"
#include "trace_io.hpp"

#include <algorithm>
#include <charconv>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <vector>

namespace {
using namespace llmatch;
using Clock = std::chrono::steady_clock;
using Nanoseconds = std::chrono::nanoseconds;
constexpr std::uint64_t hash_basis = 14695981039346656037ULL;
constexpr std::uint64_t hash_prime = 1099511628211ULL;

struct Options {
    std::filesystem::path config, setup, input, output;
    std::size_t repeats = 5;
};

struct InputHashes {
    std::string config, setup, input;
    bool operator==(const InputHashes&) const = default;
};

InputHashes input_hashes(const Options& opts) {
    return {trace::file_hash(opts.config), trace::file_hash(opts.setup), trace::file_hash(opts.input)};
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
        else if (key == "--output-dir") result.output = value;
        else if (key == "--repeats") {
            const auto parsed = std::from_chars(value.data(), value.data() + value.size(), result.repeats);
            if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size() || result.repeats == 0) {
                throw std::runtime_error("repeats must be a positive integer");
            }
        } else throw std::runtime_error("unknown option " + key);
    }
    if (result.config.empty() || result.setup.empty() || result.input.empty() || result.output.empty()) {
        throw std::runtime_error("usage: bench_core --config FILE --setup FILE --input FILE [--repeats N] --output-dir DIR");
    }
    return result;
}

struct Counts {
    std::uint64_t completed{}, accepted{}, rejected{}, trades{}, events{};
    std::uint64_t checksum = hash_basis;
    bool operator==(const Counts&) const = default;
};

// Observable consumption of every returned field. Throughput includes this
// harness work; latency stops its clock before consumption.
void consume(Counts& counts, std::span<const Event> events) {
    const auto mix = [&](std::uint64_t value) { counts.checksum = (counts.checksum ^ value) * hash_prime; };
    counts.events += events.size();
    for (const auto& event : events) {
        counts.accepted += event.kind == EventKind::Accepted;
        counts.rejected += event.kind == EventKind::Rejected;
        counts.trades += event.kind == EventKind::Trade;
        counts.completed += event.kind == EventKind::CommandComplete;
        mix(static_cast<std::uint64_t>(event.kind));
        mix(static_cast<std::uint64_t>(event.command_kind));
        mix(event.command_seq); mix(event.event_seq); mix(event.client); mix(event.request); mix(event.order_id);
        mix(static_cast<std::uint64_t>(event.reject_reason));
        mix(static_cast<std::uint64_t>(event.cancel_reason));
        mix(static_cast<std::uint64_t>(event.completion));
        mix(static_cast<std::uint64_t>(event.side));
        mix(static_cast<std::uint64_t>(event.price));
        mix(event.qty); mix(event.arrival_seq); mix(event.maker_id); mix(event.taker_id);
        mix(event.maker_client); mix(event.taker_client); mix(event.maker_arrival_seq); mix(event.taker_arrival_seq);
        mix(event.filled_qty); mix(event.resting_qty); mix(event.cancelled_qty);
    }
}

std::string hex(std::uint64_t value) {
    std::ostringstream output;
    output << std::hex << std::setfill('0') << std::setw(16) << value;
    return output.str();
}

std::ofstream output_file(const std::filesystem::path& path) {
    std::ofstream output(path);
    if (!output) throw std::runtime_error("cannot open output " + path.string());
    return output;
}

void finish(std::ofstream& output) {
    output.close();
    if (!output) throw std::runtime_error("benchmark output write failed");
}

std::string save_snapshot(const std::filesystem::path& path, const BookSnapshot& book) {
    auto output = output_file(path);
    trace::write_snapshot(output, book);
    finish(output);
    return trace::file_hash(path);
}

std::span<const Event> process(MatchingEngine& engine, const Command& command, std::vector<Event>& sink) {
    const auto result = engine.process(command, sink);
    if (result.status != ProcessStatus::Processed) throw std::runtime_error("benchmark process call failed");
    return {sink.data(), result.event_count};
}

void setup_engine(MatchingEngine& engine, std::span<const Command> setup, std::vector<Event>& sink) {
    for (const auto& command : setup) (void)process(engine, command, sink);
}

struct Sample {
    std::uint64_t ns{}, event_count{}, trade_count{};
    CommandKind command_kind{};
    CompletionStatus result{};
    RejectReason reject_reason{};
};

Sample describe(std::span<const Event> events) {
    Sample result;
    result.event_count = events.size();
    result.command_kind = events.front().command_kind;
    result.result = events.back().completion;
    result.reject_reason = events.front().reject_reason;
    for (const auto& event : events) result.trade_count += event.kind == EventKind::Trade;
    return result;
}

struct Characteristics {
    Sample result;
    std::uint64_t swept_levels{}, live_orders{};
};

// This event ledger runs only during verification. No snapshot or tracking-map
// operation is part of a timed loop.
class Ledger {
public:
    Characteristics observe(std::span<const Event> events) {
        Characteristics metric;
        metric.result = describe(events);
        Price last_trade_price = 0;
        for (const auto& event : events) {
            if (event.kind == EventKind::Rested) {
                if (!live_.emplace(event.order_id, event.qty).second) throw std::runtime_error("duplicate ledger rest");
            } else if (event.kind == EventKind::Trade) {
                auto& remaining = live_.at(event.maker_id);
                if (event.qty > remaining) throw std::runtime_error("ledger fill exceeds remaining");
                remaining -= event.qty;
                if (remaining == 0) live_.erase(event.maker_id);
                if (event.price != last_trade_price) ++metric.swept_levels;
                last_trade_price = event.price;
            } else if (event.kind == EventKind::Cancelled && event.cancel_reason == CancelReason::UserCancel) {
                if (live_.at(event.order_id) != event.qty) throw std::runtime_error("ledger cancel quantity differs");
                live_.erase(event.order_id);
            }
        }
        metric.live_orders = live_.size();
        return metric;
    }
    std::size_t size() const { return live_.size(); }
private:
    std::map<OrderId, Quantity> live_;
};

struct Verification {
    Counts counts;
    BookSnapshot final_snapshot;
    std::vector<Characteristics> characteristics;
    std::size_t setup_live_orders{}, end_live_orders{};
};

Verification verify(EngineConfig config, std::span<const Command> setup, std::span<const Command> input) {
    MatchingEngine baseline(config);
    ReferenceEngine reference(config);
    std::vector<Event> a(baseline.required_event_capacity()), b(reference.required_event_capacity());
    Ledger ledger;
    Verification verified;
    verified.characteristics.reserve(input.size());
    const auto step = [&](const Command& command, std::size_t index, const char* phase) {
        const auto actual = baseline.process(command, a);
        const auto expected = reference.process(command, b);
        if (actual.status != ProcessStatus::Processed || actual != expected ||
            !std::equal(a.begin(), a.begin() + static_cast<std::ptrdiff_t>(actual.event_count), b.begin())) {
            throw std::runtime_error(std::string("baseline/reference event mismatch in ") + phase + " at command " + std::to_string(index));
        }
        return std::span<const Event>(a.data(), actual.event_count);
    };
    for (std::size_t i = 0; i < setup.size(); ++i) (void)ledger.observe(step(setup[i], i, "setup"));
    if (baseline.snapshot() != reference.snapshot()) throw std::runtime_error("setup snapshot mismatch");
    verified.setup_live_orders = ledger.size();
    for (std::size_t i = 0; i < input.size(); ++i) {
        const auto events = step(input[i], i, "input");
        consume(verified.counts, events);
        verified.characteristics.push_back(ledger.observe(events));
    }
    baseline.check_invariants();
    reference.check_invariants();
    verified.final_snapshot = baseline.snapshot();
    if (verified.final_snapshot != reference.snapshot()) throw std::runtime_error("final snapshot mismatch");
    verified.end_live_orders = ledger.size();
    return verified;
}

std::uint64_t percentile(std::vector<std::uint64_t> data, std::size_t percent) {
    std::sort(data.begin(), data.end());
    // ceil(percent * n / 100), avoiding overflow in percent * n.
    const auto rank = (data.size() / 100) * percent + ((data.size() % 100) * percent + 99) / 100;
    return data.at(rank - 1);
}

void counts_json(std::ostream& output, const Counts& counts) {
    output << "\"completed\":" << counts.completed << ",\"accepted\":" << counts.accepted
           << ",\"rejected\":" << counts.rejected << ",\"trades\":" << counts.trades
           << ",\"events\":" << counts.events << ",\"checksum\":\"" << hex(counts.checksum) << "\"";
}

void distribution_json(std::ostream& output, const std::vector<std::uint64_t>& values) {
    const auto [smallest, largest] = std::minmax_element(values.begin(), values.end());
    const auto mean = std::accumulate(values.begin(), values.end(), 0.0L) / static_cast<long double>(values.size());
    output << "{\"min\":" << *smallest << ",\"max\":" << *largest << ",\"mean\":" << mean
           << ",\"p50\":" << percentile(values, 50) << ",\"p99\":" << percentile(values, 99) << "}";
}

void save_characteristics(const std::filesystem::path& path, const Verification& verified) {
    auto output = output_file(path);
    output << "index,command_kind,result,reject_reason,event_count,trade_count,swept_levels,live_orders\n";
    for (std::size_t i = 0; i < verified.characteristics.size(); ++i) {
        const auto& metric = verified.characteristics[i];
        const auto& sample = metric.result;
        output << i << ',' << static_cast<unsigned>(sample.command_kind) << ',' << static_cast<unsigned>(sample.result)
               << ',' << static_cast<unsigned>(sample.reject_reason) << ',' << sample.event_count << ',' << sample.trade_count
               << ',' << metric.swept_levels << ',' << metric.live_orders << '\n';
    }
    finish(output);
}

void save_samples(const std::filesystem::path& path, const std::vector<Sample>& samples) {
    auto output = output_file(path);
    output << "index,command_kind,result,reject_reason,event_count,trade_count,ns\n";
    for (std::size_t i = 0; i < samples.size(); ++i) {
        const auto& sample = samples[i];
        output << i << ',' << static_cast<unsigned>(sample.command_kind) << ',' << static_cast<unsigned>(sample.result)
               << ',' << static_cast<unsigned>(sample.reject_reason) << ',' << sample.event_count << ',' << sample.trade_count
               << ',' << sample.ns << '\n';
    }
    finish(output);
}

struct Usage {
    std::uint64_t user_us{}, system_us{}, max_rss_bytes{};
};

Usage usage() {
    rusage value{};
    if (getrusage(RUSAGE_SELF, &value) != 0) throw std::runtime_error("getrusage failed");
    const auto micros = [](timeval time) {
        return static_cast<std::uint64_t>(time.tv_sec) * 1000000 + static_cast<std::uint64_t>(time.tv_usec);
    };
#ifdef __APPLE__
    const auto rss = static_cast<std::uint64_t>(value.ru_maxrss);
#else
    const auto rss = static_cast<std::uint64_t>(value.ru_maxrss) * 1024;
#endif
    return {micros(value.ru_utime), micros(value.ru_stime), rss};
}

struct Round {
    std::size_t number{};
    bool latency{};
    Counts counts;
    std::uint64_t elapsed_ns{}, batch_elapsed_ns{}, p50_ns{}, p99_ns{};
    Usage resources;
    std::string snapshot_hash, samples_file;
};

Round measure(EngineConfig config, std::span<const Command> setup, std::span<const Command> input,
              const Verification& verified, const Options& opts, std::size_t number, bool latency,
              std::vector<Event>& sink, std::vector<Sample>& samples) {
    MatchingEngine engine(config);
    setup_engine(engine, setup, sink);
    Round round;
    round.number = number;
    round.latency = latency;
    const auto before = usage();
    const auto batch_start = Clock::now();
    if (latency) {
        for (std::size_t i = 0; i < input.size(); ++i) {
            const auto begin = Clock::now();
            const auto result = engine.process(input[i], sink);
            const auto end = Clock::now();
            if (result.status != ProcessStatus::Processed) throw std::runtime_error("latency process call failed");
            const std::span<const Event> events(sink.data(), result.event_count);
            consume(round.counts, events);
            samples[i] = describe(events);
            samples[i].ns = static_cast<std::uint64_t>(std::chrono::duration_cast<Nanoseconds>(end - begin).count());
        }
    } else {
        for (const auto& command : input) consume(round.counts, process(engine, command, sink));
    }
    const auto batch_end = Clock::now();
    const auto after = usage();
    round.batch_elapsed_ns = static_cast<std::uint64_t>(std::chrono::duration_cast<Nanoseconds>(batch_end - batch_start).count());
    round.resources = {after.user_us - before.user_us, after.system_us - before.system_us, after.max_rss_bytes};

    if (round.counts != verified.counts) throw std::runtime_error("timed round counts/checksum differ from verification");
    engine.check_invariants();
    const auto final = engine.snapshot();
    if (final != verified.final_snapshot) throw std::runtime_error("timed round final snapshot differs from verification");
    const auto name = std::string(latency ? "latency_" : "throughput_") + std::to_string(number);
    round.snapshot_hash = save_snapshot(opts.output / (name + ".snapshot"), final);
    if (latency) {
        std::vector<std::uint64_t> durations;
        durations.reserve(samples.size());
        for (const auto& sample : samples) {
            durations.push_back(sample.ns);
            round.elapsed_ns += sample.ns;
        }
        round.p50_ns = percentile(durations, 50);
        round.p99_ns = percentile(durations, 99);
        round.samples_file = name + ".csv";
        save_samples(opts.output / round.samples_file, samples);
    } else round.elapsed_ns = round.batch_elapsed_ns;
    return round;
}

void save_summary(const Options& opts, EngineConfig config, const Verification& verified,
                  const InputHashes& hashes, const std::string& snapshot_hash, const std::vector<Round>& rounds) {
    auto output = output_file(opts.output / "summary.json");
    output << std::setprecision(12);
    output << "{\n\"schema_version\":1,\"hash_algorithm\":\"fnv1a64\",\n"
           << "\"config_hash\":\"" << hashes.config << "\",\n"
           << "\"input_hash\":\"" << hashes.input << "\",\n"
           << "\"setup_hash\":\"" << hashes.setup << "\",\n"
           << "\"max_live_orders\":" << config.max_live_orders << ",\"repeats\":" << opts.repeats << ",\n"
           << "\"sink_capacity\":" << config.max_live_orders + 4 << ",\"sink_bytes\":" << (config.max_live_orders + 4) * sizeof(Event) << ",\n"
           << "\"event_bytes\":" << sizeof(Event) << ",\"quantile_method\":\"nearest-rank\",\n"
           << "\"p99_sample_warning\":\"Fewer than 100000 samples per round is below the reporting sample threshold. Meeting the threshold does not establish statistical stability. No p99.9 is reported.\",\n"
           << "\"resource_scope\":\"CPU deltas include the timed loop and harness; RSS is process high-water mark including verification, parsed input, warmup and earlier rounds. macOS bytes; Linux KiB converted to bytes.\",\n"
           << "\"timing_scope\":\"latency elapsed_ns=sum(process samples); batch_elapsed_ns includes per-command clocks, checks, consumption and recording. throughput includes process plus per-command status checks and consumption of every event field. No constant overhead subtraction.\",\n"
           << "\"verification\":{\"passed\":true,\"final_snapshot_hash\":\"" << snapshot_hash << "\",";
    counts_json(output, verified.counts);
    output << ",\"setup_live_orders\":" << verified.setup_live_orders << ",\"end_live_orders\":" << verified.end_live_orders
           << ",\"characteristics_file\":\"verification.csv\",\"snapshot_checks\":\"after setup and final input; full events compared after every command\"";
    std::vector<std::uint64_t> live, trades, levels, events;
    for (const auto& metric : verified.characteristics) {
        live.push_back(metric.live_orders); trades.push_back(metric.result.trade_count);
        levels.push_back(metric.swept_levels); events.push_back(metric.result.event_count);
    }
    output << ",\"live_orders\":"; distribution_json(output, live);
    output << ",\"trades_per_command\":"; distribution_json(output, trades);
    output << ",\"swept_levels_per_command\":"; distribution_json(output, levels);
    output << ",\"events_per_command\":"; distribution_json(output, events);
    output << "},\n\"rounds\":[\n";
    for (std::size_t i = 0; i < rounds.size(); ++i) {
        if (i != 0) output << ",\n";
        const auto& round = rounds[i];
        output << "{\"round\":" << round.number << ",\"mode\":\"" << (round.latency ? "latency" : "throughput")
               << "\",\"verified\":true,\"final_snapshot_hash\":\"" << round.snapshot_hash << "\",";
        counts_json(output, round.counts);
        output << ",\"elapsed_ns\":" << round.elapsed_ns << ",\"batch_elapsed_ns\":" << round.batch_elapsed_ns
               << ",\"p50_ns\":";
        if (round.latency) output << round.p50_ns; else output << "null";
        output << ",\"p99_ns\":";
        if (round.latency) output << round.p99_ns; else output << "null";
        output << ",\"p99_sample_threshold_met\":" << (round.latency && verified.counts.completed >= 100000 ? "true" : "false")
               << ",\"samples_file\":";
        if (round.latency) output << '"' << round.samples_file << '"'; else output << "null";
        output << ",\"max_rss_bytes\":" << round.resources.max_rss_bytes << ",\"cpu_user_us\":" << round.resources.user_us
               << ",\"cpu_system_us\":" << round.resources.system_us << '}';
    }
    output << "\n]}\n";
    finish(output);
}

int run(int argc, char** argv) {
#ifndef NDEBUG
    throw std::runtime_error("bench_core requires a Release build with NDEBUG");
#endif
#if defined(__SANITIZE_ADDRESS__)
    throw std::runtime_error("bench_core requires a build without sanitizers");
#elif defined(__has_feature)
#if __has_feature(address_sanitizer) || __has_feature(undefined_behavior_sanitizer)
    throw std::runtime_error("bench_core requires a build without sanitizers");
#endif
#endif
    const auto opts = options(argc, argv);
    std::filesystem::create_directories(opts.output);
    // A successful summary must not survive a failed rerun in this directory.
    std::filesystem::remove(opts.output / "summary.json");
    const auto hashes = input_hashes(opts);
    const auto config = trace::read_config(opts.config);
    const auto setup = trace::read_trace(opts.setup);
    const auto input = trace::read_trace(opts.input);
    if (input.empty()) throw std::runtime_error("benchmark input must contain at least one command");
    const auto verified = verify(config, setup, input);
    const auto snapshot_hash = save_snapshot(opts.output / "verified_final.snapshot", verified.final_snapshot);
    save_characteristics(opts.output / "verification.csv", verified);
    std::vector<Event> sink(config.max_live_orders + 4);
    std::vector<Sample> samples(input.size());
    {
        MatchingEngine warmup(config);
        setup_engine(warmup, setup, sink);
        Counts counts;
        for (const auto& command : input) consume(counts, process(warmup, command, sink));
        if (counts != verified.counts || warmup.snapshot() != verified.final_snapshot) throw std::runtime_error("warmup verification failed");
    }
    std::vector<Round> rounds;
    rounds.reserve(opts.repeats * 2);
    for (std::size_t i = 1; i <= opts.repeats; ++i) {
        rounds.push_back(measure(config, setup, input, verified, opts, i, true, sink, samples));
        rounds.push_back(measure(config, setup, input, verified, opts, i, false, sink, samples));
    }
    if (input_hashes(opts) != hashes) throw std::runtime_error("benchmark input files changed during the run");
    save_summary(opts, config, verified, hashes, snapshot_hash, rounds);
    std::cout << "verified " << input.size() << " commands; " << opts.repeats << " latency/throughput pairs; "
              << (opts.output / "summary.json") << '\n';
    return 0;
}
} // namespace

int main(int argc, char** argv) {
    try { return run(argc, argv); }
    catch (const std::exception& error) {
        std::cerr << "bench_core: " << error.what() << '\n';
        return 1;
    }
}
