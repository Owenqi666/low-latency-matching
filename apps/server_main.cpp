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

void outbound_header(std::ostream& out) {
    out << "client,bytes,frames,in_flight_bytes,in_flight_frames,max_bytes,max_frames,"
           "max_in_flight_bytes,max_in_flight_frames,write_operations,write_callbacks,"
           "write_error_callbacks,last_write_started_ns,last_callback_ns\n";
}

void outbound_fields(std::ostream& out, const OutboundObservation& value) {
    out << value.client << ',' << value.bytes << ',' << value.frames << ','
        << value.in_flight_bytes << ',' << value.in_flight_frames << ','
        << value.max_bytes << ',' << value.max_frames << ',' << value.max_in_flight_bytes << ','
        << value.max_in_flight_frames << ',' << value.write_operations << ',' << value.write_callbacks << ','
        << value.write_error_callbacks << ',' << value.last_write_started_ns << ',' << value.last_callback_ns << '\n';
}

void histogram_json(std::ostream& out, const DurationHistogram& value) {
    out << "{\"count\":" << value.count << ",\"maximum_ns\":" << value.maximum_ns << ",\"buckets\":[";
    for (std::size_t i = 0; i < value.buckets.size(); ++i) {
        if (i) out << ',';
        out << value.buckets[i];
    }
    out << "]}";
}

void write_diagnostics(const GatewayDiagnostics& diagnostics, const std::filesystem::path& directory) {
    std::ofstream report(directory / "gateway_diagnostics.json");
    report << "{\"schema_version\":1,\"clock\":\"server_steady_clock_ns\","
              "\"histogram_buckets\":\"bucket 0: 0..1 ns; bucket k: 2^k..2^(k+1)-1 ns\","
              "\"retention\":\"first N records; overflow counted; no catch-up timer callbacks\","
              "\"outbound_accounting\":\"bytes/frames include in-flight; queued-only equals total minus in-flight\","
              "\"write_timing_scope\":\"whole composed write completion, including error and late callbacks\","
              "\"loop_timing_scope\":\"Gateway timer lateness; not kernel wakeup latency\","
              "\"sample_period_ns\":" << GatewayDiagnostics::sample_period_ns
           << ",\"storage_bytes\":" << sizeof(GatewayDiagnostics)
           << ",\"close_capacity\":" << GatewayDiagnostics::close_capacity
           << ",\"close_count\":" << diagnostics.closes.size
           << ",\"close_overflow\":" << diagnostics.closes.overflow
           << ",\"window_capacity\":" << GatewayDiagnostics::window_capacity
           << ",\"window_count\":" << diagnostics.windows.size
           << ",\"window_overflow\":" << diagnostics.windows.overflow
           << ",\"connection_window_capacity\":" << GatewayDiagnostics::connection_window_capacity
           << ",\"connection_window_count\":" << diagnostics.connections.size
           << ",\"connection_window_overflow\":" << diagnostics.connections.overflow
           << ",\"first_connection_window_ns\":" << (diagnostics.connections.size ? diagnostics.connections.records[0].observed_ns : 0)
           << ",\"last_retained_connection_window_ns\":" << (diagnostics.connections.size ? diagnostics.connections.records[diagnostics.connections.size - 1].observed_ns : 0)
           << ",\"first_retained_close_ns\":" << (diagnostics.closes.size ? diagnostics.closes.records[0].closed_ns : 0)
           << ",\"last_retained_close_ns\":" << (diagnostics.closes.size ? diagnostics.closes.records[diagnostics.closes.size - 1].closed_ns : 0)
           << ",\"first_window_ns\":" << (diagnostics.windows.size ? diagnostics.windows.records[0].observed_ns : 0)
           << ",\"last_retained_window_ns\":" << (diagnostics.windows.size ? diagnostics.windows.records[diagnostics.windows.size - 1].observed_ns : 0)
           << ",\"last_observed_window_ns\":" << diagnostics.previous_window.observed_ns
           << ",\"whole_write_completion\":";
    histogram_json(report, diagnostics.whole_write_completion);
    report << ",\"callback_interval\":";
    histogram_json(report, diagnostics.callback_interval);
    report << ",\"loop_lateness\":";
    histogram_json(report, diagnostics.loop_lateness);
    report << "}\n";
    std::ofstream closes(directory / "gateway_closes.csv");
    closes << "closed_ns,reason,";
    outbound_header(closes);
    for (std::size_t i = 0; i < diagnostics.closes.size; ++i) {
        const auto& record = diagnostics.closes.records[i];
        closes << record.closed_ns << ',' << close_reason_name(static_cast<CloseReason>(record.reason)) << ',';
        outbound_fields(closes, record.outbound);
    }
    std::ofstream connections(directory / "gateway_connections.csv");
    connections << "observed_ns,";
    outbound_header(connections);
    for (std::size_t i = 0; i < diagnostics.connections.size; ++i) {
        const auto& record = diagnostics.connections.records[i];
        connections << record.observed_ns << ',';
        outbound_fields(connections, record.outbound);
    }
    std::ofstream windows(directory / "gateway_windows.csv");
    windows << "planned_ns,observed_ns,command_depth,event_depth,connections,admitted,events_consumed,"
               "bbo_consumed,write_operations,write_callbacks,bytes_transferred,write_operations_delta,"
               "write_callbacks_delta,bytes_transferred_delta\n";
    for (std::size_t i = 0; i < diagnostics.windows.size; ++i) {
        const auto& w = diagnostics.windows.records[i];
        windows << w.planned_ns << ',' << w.observed_ns << ',' << w.command_depth << ',' << w.event_depth << ','
                << w.connections << ',' << w.admitted << ',' << w.events_consumed << ',' << w.bbo_consumed << ','
                << w.write_operations << ',' << w.write_callbacks << ',' << w.bytes_transferred << ','
                << w.write_operations_delta << ',' << w.write_callbacks_delta << ',' << w.bytes_transferred_delta << '\n';
    }
    if (!report || !closes || !connections || !windows) throw std::runtime_error("cannot write Gateway diagnostics");
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
           << ",\"gateway_diagnostics_enabled\":" << (config.gateway_diagnostics ? "true" : "false")
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
    if (const auto* diagnostics = server.diagnostics()) write_diagnostics(*diagnostics, directory);
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
                             "  [--gateway-diagnostics 0|1] (bounded detailed observations; default off)\n"
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
            else if (option == "--gateway-diagnostics") {
                const auto enabled = number<unsigned>(value);
                if (enabled > 1) throw std::invalid_argument("gateway-diagnostics must be 0 or 1");
                config.gateway_diagnostics = enabled != 0;
            }
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
