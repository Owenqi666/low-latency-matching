#include <algorithm>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using Clock = std::chrono::steady_clock;
using Nanoseconds = std::chrono::nanoseconds;
constexpr std::size_t sample_count = 100000;

std::uint64_t ns(Clock::duration duration) {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<Nanoseconds>(duration).count());
}

std::uint64_t quantile(std::vector<std::uint64_t> data, std::size_t percent) {
    std::sort(data.begin(), data.end());
    return data[(data.size() * percent + 99) / 100 - 1];
}

int run(int argc, char** argv) {
    if (argc != 3 || std::string(argv[1]) != "--output") throw std::runtime_error("usage: clock_probe --output FILE");
    const std::filesystem::path path = argv[2];
    std::vector<std::uint64_t> intervals(sample_count);
    std::vector<Clock::time_point> recorded(sample_count);
    for (std::size_t i = 0; i < 1000; ++i) (void)Clock::now();
    const auto pair_start = Clock::now();
    for (auto& interval : intervals) {
        const auto before = Clock::now();
        const auto after = Clock::now();
        interval = ns(after - before);
    }
    const auto pair_elapsed = ns(Clock::now() - pair_start);
    const auto record_start = Clock::now();
    for (auto& sample : recorded) sample = Clock::now();
    const auto record_elapsed = ns(Clock::now() - record_start);
    std::uint64_t minimum_positive = std::numeric_limits<std::uint64_t>::max();
    std::size_t zero_intervals = 0;
    for (const auto interval : intervals) {
        if (interval == 0) ++zero_intervals;
        else minimum_positive = std::min(minimum_positive, interval);
    }
    // Consume recorded timestamps after timing so their stores stay observable.
    std::uint64_t recorded_checksum = 14695981039346656037ULL;
    for (const auto timestamp : recorded) {
        recorded_checksum = (recorded_checksum ^ ns(timestamp.time_since_epoch())) * 1099511628211ULL;
    }
    if (!path.parent_path().empty()) std::filesystem::create_directories(path.parent_path());
    std::ofstream output(path);
    if (!output) throw std::runtime_error("cannot open " + path.string());
    output << "{\n\"schema_version\":1,\"clock\":\"std::chrono::steady_clock\",\"is_steady\":" << (Clock::is_steady ? "true" : "false")
           << ",\"samples\":" << sample_count << ",\n\"nominal_period_num\":" << Clock::period::num
           << ",\"nominal_period_den\":" << Clock::period::den << ",\"minimum_positive_interval_ns\":";
    if (zero_intervals == sample_count) output << "null"; else output << minimum_positive;
    output << ",\"zero_intervals\":" << zero_intervals << ",\n\"back_to_back_p50_ns\":" << quantile(intervals, 50)
           << ",\"back_to_back_p99_ns\":" << quantile(intervals, 99)
           << ",\"pair_and_duration_record_batch_ns\":" << pair_elapsed
           << ",\"pair_and_duration_record_mean_ns\":" << static_cast<double>(pair_elapsed) / sample_count
           << ",\n\"clock_and_timestamp_record_batch_ns\":" << record_elapsed
           << ",\"clock_and_timestamp_record_mean_ns\":" << static_cast<double>(record_elapsed) / sample_count
           << ",\"recorded_checksum\":" << recorded_checksum
           << ",\n\"method\":\"100000 back-to-back clock pairs, then a separate batch storing one clock timestamp per sample; vectors preallocated; nearest-rank quantiles; empirical resolution differs from nominal period; no constant is subtracted from benchmark samples.\"\n}\n";
    output.close();
    if (!output) throw std::runtime_error("clock probe output write failed");
    std::cout << "clock probe saved " << path << '\n';
    return 0;
}
} // namespace

int main(int argc, char** argv) {
    try { return run(argc, argv); }
    catch (const std::exception& error) {
        std::cerr << "clock_probe: " << error.what() << '\n';
        return 1;
    }
}
