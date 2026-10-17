#include "llmatch/server.hpp"
#include "trace_io.hpp"

#include <charconv>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string_view>
#include <sys/resource.h>
#include <sys/utsname.h>

namespace {
using namespace llmatch;
template<class T> T number(std::string_view text) {
    T result{};
    const auto parsed = std::from_chars(text.data(), text.data() + text.size(), result);
    if (parsed.ec != std::errc{} || parsed.ptr != text.data() + text.size()) {
        throw std::invalid_argument("invalid numeric option: " + std::string(text));
    }
    return result;
}

std::string json_string(const std::string& value) {
    std::ostringstream out;
    out << '"';
    for (const char character : value) {
        const auto c = static_cast<unsigned char>(character);
        if (c == '"' || c == '\\') out << '\\' << c;
        else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << unsigned(c);
        else out << c;
    }
    out << '"';
    return out.str();
}

void write_evidence(const MatchingServer& server, const std::filesystem::path& directory,
                    int exit_status, std::uint64_t started, std::uint64_t ended) {
    rusage usage{};
    getrusage(RUSAGE_SELF, &usage); // Before allocating/formatting evidence files.
    std::filesystem::create_directories(directory);
    const auto& pipeline = server.pipeline();
    const auto& config = server.config();
    const auto& stats = server.stats();
    const auto& matching = pipeline.stats();
    std::vector<Command> commands;
    commands.reserve(pipeline.admissions().size());
    for (const auto& record : pipeline.admissions()) commands.push_back(record.command);
    trace::write_config(directory / "engine.config", config.pipeline.engine);
    trace::write_trace(directory / "admitted.trace", commands);
    std::ofstream snapshot(directory / "final.snapshot");
    trace::write_snapshot(snapshot, pipeline.final_snapshot());
    std::ofstream samples(directory / "service_samples.csv");
    samples << "command_seq,client,request,order_id,admitted_ns,gateway_wait_ns,completed_ns,service_ns,events,trades,checksum,status\n";
    for (std::size_t i = 0; i < pipeline.completions().size(); ++i) {
        const auto& accepted = pipeline.admissions()[i];
        const auto& sample = pipeline.completions()[i];
        samples << sample.command_seq << ',' << accepted.command.client << ',' << accepted.command.request
                << ',' << order_id(accepted.command) << ',' << sample.admitted_ns << ',' << accepted.gateway_wait_ns
                << ',' << sample.completed_ns << ',' << sample.completed_ns - sample.admitted_ns
                << ',' << sample.events << ',' << sample.trades << ',' << sample.checksum
                << ',' << static_cast<unsigned>(sample.status) << '\n';
    }
    utsname system{};
    uname(&system);
    auto rss_bytes = static_cast<std::uint64_t>(usage.ru_maxrss);
#ifndef __APPLE__
    rss_bytes *= 1024;
#endif
    std::ofstream report(directory / "server.json");
    report << "{\n\"schema_version\":1,\"exit_status\":" << exit_status
           << ",\"failure\":" << json_string(server.failure())
           << ",\"started_ns\":" << started << ",\"ended_ns\":" << ended
           << ",\"os\":" << json_string(system.sysname)
           << ",\"kernel\":" << json_string(system.release)
           << ",\"arch\":" << json_string(system.machine)
           << ",\"compiler\":" << json_string(__VERSION__)
           << ",\"peak_rss_bytes\":" << rss_bytes
           << ",\"user_cpu_us\":" << usage.ru_utime.tv_sec * 1000000LL + usage.ru_utime.tv_usec
           << ",\"system_cpu_us\":" << usage.ru_stime.tv_sec * 1000000LL + usage.ru_stime.tv_usec
           << ",\"command_capacity\":" << config.pipeline.command_capacity
           << ",\"event_capacity\":" << config.pipeline.event_capacity
           << ",\"record_limit\":" << config.pipeline.record_limit
           << ",\"send_limit\":" << config.send_limit
           << ",\"max_connections\":" << config.max_connections
           << ",\"socket_send_buffer\":" << config.socket_send_buffer
           << ",\"shutdown_ms\":" << config.shutdown_timeout.count()
           << ",\"admitted\":" << pipeline.admitted()
           << ",\"completed\":" << matching.completed
           << ",\"uncompleted\":" << pipeline.admitted() - matching.completed
           << ",\"current_admission\":" << matching.current_admission
           << ",\"worker_phase\":" << json_string(matching.phase)
           << ",\"worker_aborted\":" << (pipeline.aborted() ? "true" : "false")
           << ",\"events_published\":" << matching.events
           << ",\"bbo_published\":" << matching.bbo_updates
           << ",\"last_event_seq\":" << matching.last_event_seq
           << ",\"events_consumed\":" << stats.consumed_events
           << ",\"bbo_consumed\":" << stats.consumed_bbo
           << ",\"command_high_water\":" << pipeline.command_high_water()
           << ",\"event_high_water\":" << matching.event_high_water
           << ",\"output_waits\":" << matching.output_waits
           << ",\"send_high_water\":" << stats.send_high_water
           << ",\"connections\":" << stats.connections
           << ",\"connection_limit_rejections\":" << stats.connection_limit_rejections
           << ",\"missing_business_recipients\":" << stats.missing_business_recipients
           << ",\"written_business_frames\":" << stats.written_business_frames
           << ",\"written_frames\":" << stats.written_frames
           << ",\"discarded_business_frames\":" << stats.discarded_business_frames
           << ",\"discarded_frames\":" << stats.discarded_frames
           << ",\"write_stats_scope\":\"server_lifetime_including_setup\""
           << ",\"write_batch_max_frames\":" << stats.write_batch_max_frames
           << ",\"write_batch_max_bytes\":" << stats.write_batch_max_bytes
           << ",\"write_operations\":" << stats.write_operations
           << ",\"write_callbacks\":" << stats.write_callbacks
           << ",\"write_error_callbacks\":" << stats.write_error_callbacks
           << ",\"write_frames_submitted\":" << stats.write_frames_submitted
           << ",\"write_bytes_submitted\":" << stats.write_bytes_submitted
           << ",\"write_bytes_transferred\":" << stats.write_bytes_transferred
           << ",\"unconfirmed_write_callbacks\":" << stats.unconfirmed_write_callbacks
           << ",\"unconfirmed_write_bytes\":" << stats.unconfirmed_write_bytes
           << ",\"unconfirmed_write_complete_frames\":" << stats.unconfirmed_write_complete_frames
           << ",\"write_batch_frames\":[";
    for (std::size_t i = 0; i < stats.write_batch_frames.size(); ++i) {
        if (i) report << ',';
        report << stats.write_batch_frames[i];
    }
    report << "],\"write_batch_bytes_bucket_width\":256,\"write_batch_bytes\":[";
    for (std::size_t i = 0; i < stats.write_batch_bytes.size(); ++i) {
        if (i) report << ',';
        report << stats.write_batch_bytes[i];
    }
    report << "],\"close_reasons\":{";
    for (std::size_t i = 0; i < stats.closes.size(); ++i) {
        if (i) report << ',';
        report << json_string(close_reason_name(static_cast<CloseReason>(i))) << ':' << stats.closes[i];
    }
    report << "}}\n";
    if (!report || !samples || !snapshot) throw std::runtime_error("cannot write service evidence");
}
}

int main(int argc, char** argv) {
    try {
        ServerConfig config;
        std::filesystem::path output;
        for (int i = 1; i < argc; ++i) {
            const std::string_view option(argv[i]);
            if (option == "--help") {
                std::cout << "matching_server [--address 127.0.0.1] [--port 19999] [--capacity 1000]\n"
                             "  [--command-capacity 1024] [--event-capacity 1024] [--max-connections 64]\n"
                             "  [--send-limit 65536] [--shutdown-ms 5000] [--socket-send-buffer 0]\n"
                             "  [--max-price 20000] [--max-qty 1000000] [--record-limit 0] [--output-dir DIR]\n"
                             "SIGINT/SIGTERM stops admission and drains admitted commands. Port 0 selects a free port.\n";
                return 0;
            }
            if (++i == argc) throw std::invalid_argument("option requires a value");
            const std::string_view value(argv[i]);
            if (option == "--address") config.address = value;
            else if (option == "--port") config.port = number<std::uint16_t>(value);
            else if (option == "--capacity") config.pipeline.engine.max_live_orders = number<std::size_t>(value);
            else if (option == "--max-price") config.pipeline.engine.max_price = number<Price>(value);
            else if (option == "--max-qty") config.pipeline.engine.max_order_qty = number<Quantity>(value);
            else if (option == "--command-capacity") config.pipeline.command_capacity = number<std::size_t>(value);
            else if (option == "--event-capacity") config.pipeline.event_capacity = number<std::size_t>(value);
            else if (option == "--max-connections") config.max_connections = number<std::size_t>(value);
            else if (option == "--send-limit") config.send_limit = number<std::size_t>(value);
            else if (option == "--shutdown-ms") config.shutdown_timeout = std::chrono::milliseconds(number<std::int64_t>(value));
            else if (option == "--socket-send-buffer") config.socket_send_buffer = number<int>(value);
            else if (option == "--record-limit") config.pipeline.record_limit = number<std::size_t>(value);
            else if (option == "--output-dir") output = value;
            else throw std::invalid_argument("unknown option: " + std::string(option));
        }
        MatchingServer server(config);
        std::cout << "READY " << server.port() << '\n' << std::flush;
        const auto started = steady_now_ns();
        const int result = server.run();
        const auto ended = steady_now_ns();
        if (!output.empty()) write_evidence(server, output, result, started, ended);
        std::cout << "STOPPED admitted=" << server.pipeline().admitted()
                  << " completed=" << server.pipeline().stats().completed << '\n';
        if (result) std::cerr << server.failure() << '\n';
        return result;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
