#include "llmatch/protocol.hpp"
#include "reference_engine.hpp"
#include "trace_io.hpp"

#include <boost/json/src.hpp>
#include <array>
#include <charconv>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <sstream>
#include <stdexcept>

namespace {
constexpr const char* columns = "command_seq,client,request,order_id,admitted_ns,gateway_wait_ns,completed_ns,service_ns,events,trades,checksum,status";
std::uint64_t count(const boost::json::object& report, const char* name) {
    const auto& value = report.at(name);
    if (value.is_uint64()) return value.as_uint64();
    if (value.is_int64() && value.as_int64() >= 0) return static_cast<std::uint64_t>(value.as_int64());
    throw std::runtime_error(std::string("invalid server count: ") + name);
}
std::array<std::uint64_t, 12> row(const std::string& text) {
    std::array<std::uint64_t, 12> values{};
    std::size_t begin = 0;
    for (std::size_t i = 0; i < values.size(); ++i) {
        const auto end = text.find(',', begin);
        if ((end == std::string::npos) != (i + 1 == values.size())) throw std::runtime_error("sample column count mismatch");
        const auto stop = end == std::string::npos ? text.size() : end;
        const auto result = std::from_chars(text.data() + begin, text.data() + stop, values[i]);
        if (result.ec != std::errc{} || result.ptr != text.data() + stop) throw std::runtime_error("invalid sample integer");
        begin = stop + 1;
    }
    return values;
}
}

int main(int argc, char** argv) {
    using namespace llmatch;
    try {
        if (argc != 3 || std::string(argv[1]) != "--directory") {
            throw std::invalid_argument("usage: verify_service --directory SERVER_EVIDENCE");
        }
        const std::filesystem::path directory(argv[2]);
        std::filesystem::remove(directory / "verification.json");
        std::ifstream summary(directory / "server.json");
        if (!summary) throw std::runtime_error("missing server.json");
        const std::string summary_text{std::istreambuf_iterator<char>(summary), std::istreambuf_iterator<char>()};
        const auto server = boost::json::parse(summary_text).as_object();
        if (count(server, "schema_version") != 1 || count(server, "exit_status") != 0 ||
            !server.at("failure").as_string().empty() || count(server, "record_limit") == 0 ||
            server.at("worker_aborted").as_bool() || count(server, "current_admission") != 0 ||
            server.at("worker_phase").as_string() != "idle") {
            throw std::runtime_error("service run failed or per-command recording was disabled");
        }
        const auto config = trace::read_config(directory / "engine.config");
        const auto commands = trace::read_trace(directory / "admitted.trace");
        if (count(server, "admitted") != commands.size() || count(server, "completed") != commands.size() ||
            count(server, "uncompleted") != 0 || count(server, "record_limit") < commands.size() ||
            count(server, "events_published") != count(server, "events_consumed") ||
            count(server, "bbo_published") != count(server, "bbo_consumed")) {
            throw std::runtime_error("service counts do not describe a completely recorded and drained run");
        }
        ReferenceEngine reference(config);
        std::vector<Event> buffer(reference.required_event_capacity());
        std::ifstream samples(directory / "service_samples.csv");
        std::string line;
        if (!std::getline(samples, line) || line != columns) throw std::runtime_error("missing or invalid service sample header");
        std::uint64_t events = 0, trades = 0, accepted = 0, rejected = 0, recipients = 0;
        for (std::size_t i = 0; i < commands.size(); ++i) {
            if (!std::getline(samples, line)) throw std::runtime_error("missing sample at admitted command " + std::to_string(i + 1));
            const auto actual = row(line);
            const auto result = reference.process(commands[i], buffer);
            if (result.status != ProcessStatus::Processed) throw std::runtime_error("reference call failed");
            std::uint64_t digest = 14695981039346656037ULL, command_trades = 0;
            for (const auto& event : std::span(buffer).first(result.event_count)) {
                const auto frame = protocol::encode(event);
                for (const auto byte : frame.bytes()) digest = (digest ^ byte) * 1099511628211ULL;
                command_trades += event.kind == EventKind::Trade;
                recipients += event.kind == EventKind::Trade && event.maker_client != event.taker_client ? 2 : 1;
            }
            const auto& complete = buffer[result.event_count - 1];
            if (actual[0] != complete.command_seq || actual[1] != commands[i].client ||
                actual[2] != commands[i].request || actual[3] != order_id(commands[i]) ||
                actual[6] < actual[4] || actual[7] != actual[6] - actual[4] ||
                actual[8] != result.event_count || actual[9] != command_trades ||
                actual[10] != digest || actual[11] != static_cast<unsigned>(complete.completion)) {
                std::ostringstream expected;
                trace::write_events(expected, std::span(buffer).first(result.event_count));
                std::ofstream detail(directory / "verification-difference.txt");
                detail << "admitted command " << i + 1 << "\nactual sample: " << line
                       << "\nexpected events:\n" << expected.str();
                throw std::runtime_error("service/reference difference at admitted command " + std::to_string(i + 1));
            }
            events += result.event_count;
            trades += command_trades;
            accepted += complete.completion == CompletionStatus::Accepted;
            rejected += complete.completion == CompletionStatus::Rejected;
        }
        if (std::getline(samples, line)) throw std::runtime_error("extra service sample after admitted trace");
        if (count(server, "events_published") != events || count(server, "last_event_seq") != events) {
            throw std::runtime_error("published business event counts differ from reference");
        }
        if (count(server, "written_business_frames") + count(server, "discarded_business_frames") +
            count(server, "missing_business_recipients") != recipients) {
            throw std::runtime_error("business delivery counters do not conserve routed recipients");
        }
        reference.check_invariants();
        std::ostringstream expected_snapshot;
        trace::write_snapshot(expected_snapshot, reference.snapshot());
        std::ifstream snapshot(directory / "final.snapshot");
        const std::string actual_snapshot{std::istreambuf_iterator<char>(snapshot), std::istreambuf_iterator<char>()};
        if (actual_snapshot != expected_snapshot.str()) throw std::runtime_error("service/reference final snapshot differs");
        std::ofstream report(directory / "verification.json");
        report << "{\"schema_version\":1,\"result\":\"passed\",\"commands\":" << commands.size()
               << ",\"events\":" << events << ",\"trades\":" << trades
               << ",\"business_recipients\":" << recipients
               << ",\"accepted\":" << accepted << ",\"rejected\":" << rejected
               << ",\"admitted_trace_hash\":\"" << trace::file_hash(directory / "admitted.trace")
               << "\",\"snapshot_hash\":\"" << trace::file_hash(directory / "final.snapshot")
               << "\",\"samples_hash\":\"" << trace::file_hash(directory / "service_samples.csv")
               << "\",\"server_report_hash\":\"" << trace::file_hash(directory / "server.json")
               << "\",\"config_hash\":\"" << trace::file_hash(directory / "engine.config") << "\"}\n";
        if (!report) throw std::runtime_error("cannot write verification result");
        std::cout << "verified " << commands.size() << " admitted commands, " << events << " business events\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "verify_service: " << error.what() << '\n';
        return 1;
    }
}
