#include "llmatch/protocol.hpp"
#include "trace_io.hpp"

#include <boost/asio.hpp>
#include <algorithm>
#include <array>
#include <charconv>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <set>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

namespace {
using namespace llmatch;
namespace asio = boost::asio;
using Tcp = asio::ip::tcp;
using ErrorCode = boost::system::error_code;
using Clock = std::chrono::steady_clock;
using Ns = std::uint64_t;
constexpr Ns fnv_basis = 14695981039346656037ULL;
constexpr Ns fnv_prime = 1099511628211ULL;
Ns now_ns() { return static_cast<Ns>(std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch()).count()); }
Clock::time_point at_ns(Ns value) { return Clock::time_point(std::chrono::nanoseconds(value)); }

template<class T> T number(std::string_view text) {
    T value{};
    const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), value);
    if (error != std::errc{} || end != text.data() + text.size()) throw std::invalid_argument("invalid integer: " + std::string(text));
    return value;
}

std::string json(const std::string& text) {
    std::ostringstream out;
    out << '"';
    for (const char c : text) {
        if (c == '"' || c == '\\') out << '\\' << c;
        else if (c == '\n') out << "\\n";
        else if (static_cast<unsigned char>(c) < 32) out << '?';
        else out << c;
    }
    out << '"';
    return out.str();
}

struct Options {
    std::string host{"127.0.0.1"};
    std::string port{"19999"};
    std::size_t connections{1};
    std::size_t max_inflight{16384};
    std::size_t max_send_bytes{65536};
    std::uint64_t drain_ms{5000};
    std::filesystem::path setup, input, schedule, output;
};

std::vector<Ns> read_schedule(const std::filesystem::path& path, std::size_t expected) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("cannot open schedule: " + path.string());
    std::vector<Ns> offsets;
    offsets.reserve(expected);
    std::string line;
    std::size_t row = 0;
    while (std::getline(input, line)) {
        ++row;
        const auto first = line.find_first_not_of(" \t\r");
        const auto last = line.find_last_not_of(" \t\r");
        try {
            if (first == std::string::npos) throw std::invalid_argument("empty offset");
            const auto value = number<Ns>(std::string_view(line).substr(first, last - first + 1));
            if (!offsets.empty() && value < offsets.back()) throw std::invalid_argument("offsets must be nondecreasing");
            offsets.push_back(value);
        } catch (const std::exception& error) {
            throw std::runtime_error(path.string() + ":" + std::to_string(row) + ": " + error.what());
        }
    }
    if (!input.eof() || offsets.size() != expected) throw std::runtime_error("schedule row count must equal input command count");
    return offsets;
}

enum class State { Unscheduled, Queued, Started, Completed, Failed, Unfinished, NotStarted };
enum class Failure { None, MaxInflight, SendLimit, Disconnected, Protocol, Startup, Setup, Deadline, Write };
const char* failure_name(Failure value) {
    constexpr std::array names{"", "max_inflight", "send_limit", "disconnected", "protocol", "startup", "setup", "deadline", "write_error"};
    return names[static_cast<std::size_t>(value)];
}
const char* outcome(State value) {
    switch (value) {
        case State::Completed: return "completed";
        case State::Failed: return "failed";
        case State::Unfinished: return "unfinished";
        default: return "not_started";
    }
}
struct Item {
    Command command;
    protocol::Frame frame;
    State state{State::Unscheduled};
    Failure failure{};
    Ns first_attempt{}, write_completed{}, complete{};
    Sequence command_seq{};
    Ns events{}, trades{}, checksum{fnv_basis};
    CompletionStatus completion{};
};

// Storage is allocated before connections start. Queue operations do not grow it.
class IndexQueue {
public:
    explicit IndexQueue(std::size_t capacity) : storage_(capacity) {}
    bool empty() const { return size_ == 0; }
    std::size_t front() const { return storage_[head_]; }
    void push(std::size_t value) { storage_[(head_ + size_) % storage_.size()] = value; ++size_; }
    void pop() { head_ = (head_ + 1) % storage_.size(); --size_; }
    void clear() { head_ = size_ = 0; }
private:
    std::vector<std::size_t> storage_;
    std::size_t head_{}, size_{};
};

struct Counts {
    Ns planned{}, not_started{}, started{}, completed{}, failed{}, unfinished{}, accepted{}, rejected{};
};

class Loadgen {
    struct Connection {
        Connection(asio::io_context& io, std::size_t capacity) : socket(io), outgoing(capacity + 1), pending(capacity) {}
        Tcp::socket socket;
        IndexQueue outgoing, pending;
        std::array<std::uint8_t, 4096> received{};
        std::size_t received_size{}, send_bytes{}, send_high_water{};
        ClientId actual{};
        bool connected{}, writing{};
    };
public:
    explicit Loadgen(Options options) : options_(std::move(options)), resolver_(io_), schedule_timer_(io_), deadline_(io_) {
        auto setup = trace::read_trace(options_.setup);
        auto input = trace::read_trace(options_.input);
        setup_count_ = setup.size();
        offsets_ = read_schedule(options_.schedule, input.size());
        items_.reserve(setup.size() + input.size());
        std::set<std::pair<ClientId, RequestId>> identities;
        const auto append = [&](const std::vector<Command>& commands) {
            for (const auto& command : commands) {
                if (command.client == 0 || command.client > options_.connections)
                    throw std::invalid_argument("trace client must be a logical ID in 1..connections");
                if (!identities.emplace(command.client, command.request).second)
                    throw std::invalid_argument("RequestId must be unique per logical client across setup and input");
                items_.push_back(Item{command, protocol::encode(command)});
            }
        };
        append(setup);
        append(input);
        connections_.reserve(options_.connections);
        for (std::size_t i = 0; i < options_.connections; ++i)
            connections_.push_back(std::make_unique<Connection>(io_, options_.max_inflight));
        input_hash_ = trace::file_hash(options_.input);
        setup_hash_ = trace::file_hash(options_.setup);
        schedule_hash_ = trace::file_hash(options_.schedule);
        probe_clock();
    }

    int run() {
        if (!arm_deadline(Failure::Startup)) { write_evidence(); return exit_code_; }
        resolver_.async_resolve(options_.host, options_.port, [this](const ErrorCode& error, const Tcp::resolver::results_type& endpoints) {
            if (finished_) return;
            if (error) return finish(Failure::Startup, "resolve: " + error.message());
            for (std::size_t index = 0; index < connections_.size(); ++index) {
                asio::async_connect(connections_[index]->socket, endpoints,
                    [this, index](const ErrorCode& connect_error, const Tcp::endpoint&) {
                        if (finished_) return;
                        if (connect_error) return finish(Failure::Startup, "connect: " + connect_error.message());
                        ErrorCode option_error;
                        connections_[index]->socket.set_option(Tcp::no_delay(true), option_error);
                        if (option_error) return finish(Failure::Startup, "TCP_NODELAY: " + option_error.message());
                        connections_[index]->connected = true;
                        read(index);
                    });
            }
        });
        io_.run();
        write_evidence();
        return exit_code_;
    }

private:
    void probe_clock() {
        std::vector<Ns> records(probe_count_);
        min_interval_ = std::numeric_limits<Ns>::max();
        for (std::size_t i = 0; i < probe_count_; ++i) {
            const auto before = now_ns();
            const auto after = now_ns();
            if (after > before) min_interval_ = std::min(min_interval_, after - before);
        }
        if (min_interval_ == std::numeric_limits<Ns>::max()) min_interval_ = 0;
        const auto start = now_ns();
        for (auto& record : records) record = now_ns();
        recording_ns_ = now_ns() - start;
        probe_sink_ = records.back();
    }

    bool arm_deadline(Failure failure) {
        const auto now = now_ns();
        const auto maximum = static_cast<Ns>(std::numeric_limits<std::int64_t>::max());
        if (options_.drain_ms > (maximum - now) / 1000000) {
            finish(Failure::Startup, "deadline exceeds representable steady_clock time");
            return false;
        }
        deadline_.expires_at(at_ns(now + options_.drain_ms * 1000000));
        deadline_.async_wait([this, failure](const ErrorCode& error) {
            if (!error) finish(failure, "deadline exceeded");
        });
        return true;
    }

    void finish(Failure failure, const std::string& reason = {}) {
        if (finished_) return;
        finished_ = true;
        ended_ = now_ns();
        failure_ = reason;
        for (auto& item : items_) {
            if (item.state == State::Started) { item.state = State::Unfinished; item.failure = failure; }
            else if (item.state == State::Queued || item.state == State::Unscheduled) {
                item.state = State::NotStarted;
                item.failure = failure;
            }
        }
        deadline_.cancel();
        schedule_timer_.cancel();
        resolver_.cancel();
        for (auto& connection : connections_) {
            ErrorCode ignored;
            connection->socket.close(ignored);
        }
        const auto counts = count(setup_count_, items_.size());
        const auto setup = count(0, setup_count_);
        exit_code_ = failure != Failure::None || !failure_.empty() || counts.completed != counts.planned || setup.completed != setup.planned ? 1 : 0;
    }

    void fail_connection(std::size_t index, Failure failure, const std::string& reason) {
        auto& connection = *connections_[index];
        connection.connected = false;
        ErrorCode ignored;
        connection.socket.close(ignored);
        while (!connection.pending.empty()) {
            auto& item = items_[connection.pending.front()];
            item.state = item.first_attempt == 0 ? State::NotStarted : State::Failed;
            item.failure = failure;
            connection.pending.pop();
            --inflight_;
        }
        connection.outgoing.clear();
        connection.send_bytes = 0;
        connection.writing = false;
        if (started_ == 0) return finish(failure, reason);
        if (failure_.empty()) failure_ = reason;
        maybe_finish();
    }

    void read(std::size_t index) {
        auto& connection = *connections_[index];
        connection.socket.async_read_some(asio::buffer(connection.received.data() + connection.received_size,
            connection.received.size() - connection.received_size), [this, index](const ErrorCode& error, std::size_t count) {
                const auto received_at = now_ns();
                auto& current = *connections_[index];
                if (finished_ || !current.connected) return;
                if (error) return fail_connection(index, current.received_size == 0 ? Failure::Disconnected : Failure::Protocol,
                    (current.received_size == 0 ? "read: " : "truncated frame: ") + error.message());
                current.received_size += count;
                std::size_t consumed = 0;
                try {
                    while (consumed < current.received_size && !finished_ && current.connected) {
                        const auto bytes = std::span(current.received).subspan(consumed, current.received_size - consumed);
                        const auto info = protocol::inspect(bytes);
                        if (info.status == protocol::FrameStatus::Invalid) throw protocol::ProtocolError(info.error);
                        if (info.status == protocol::FrameStatus::NeedMore) break;
                        const auto frame = bytes.first(info.frame_size);
                        receive(index, protocol::decode(frame), frame, received_at);
                        consumed += info.frame_size;
                    }
                } catch (const std::exception& exception) {
                    return fail_connection(index, Failure::Protocol, exception.what());
                }
                if (finished_ || !current.connected) return;
                current.received_size -= consumed;
                std::memmove(current.received.data(), current.received.data() + consumed, current.received_size);
                read(index);
            });
    }

    void receive(std::size_t index, const protocol::Decoded& decoded, std::span<const std::uint8_t> frame, Ns received_at) {
        auto& connection = *connections_[index];
        if (const auto* welcome = std::get_if<protocol::Welcome>(&decoded)) {
            if (connection.actual != 0 || welcome->client == 0) throw std::runtime_error("invalid Welcome");
            connection.actual = welcome->client;
            if (++ready_ == connections_.size()) next_setup();
            return;
        }
        if (connection.actual == 0) throw std::runtime_error("expected Welcome");
        if (std::holds_alternative<Bbo>(decoded)) { ++bbo_received_; return; }
        const auto* event = std::get_if<Event>(&decoded);
        if (!event) throw std::runtime_error("server sent request frame");
        if (event->kind == EventKind::Trade && event->client != connection.actual) { ++maker_trades_; return; }
        if (connection.pending.empty()) throw std::runtime_error("event without pending request");
        const auto item_index = connection.pending.front();
        auto& item = items_[item_index];
        if (event->client != connection.actual || event->request != item.command.request ||
            event->order_id != order_id(item.command) || event->command_kind != command_kind(item.command))
            throw std::runtime_error("event request correlation mismatch");
        if (event->kind == EventKind::Accepted || event->kind == EventKind::Rejected) {
            if (item.command_seq != 0 || event->command_seq == 0) throw std::runtime_error("invalid acknowledgement");
            item.command_seq = event->command_seq;
        } else if (item.command_seq == 0 || item.command_seq != event->command_seq) {
            throw std::runtime_error("event command sequence mismatch");
        }
        for (const auto byte : frame) { item.checksum ^= byte; item.checksum *= fnv_prime; }
        ++item.events;
        if (event->kind == EventKind::Trade) ++item.trades;
        if (event->kind == EventKind::CommandComplete) {
            if (event->completion == CompletionStatus::None) throw std::runtime_error("Complete has no terminal status");
            item.complete = received_at;
            item.completion = event->completion;
            item.state = State::Completed;
            connection.pending.pop();
            --inflight_;
            if (item_index < setup_count_) { ++setup_next_; next_setup(); }
            else maybe_finish();
        }
    }

    bool enqueue(std::size_t index) {
        auto& item = items_[index];
        auto& connection = *connections_[item.command.client - 1];
        Failure failure = Failure::None;
        if (!connection.connected) failure = Failure::Disconnected;
        else if (inflight_ == options_.max_inflight) failure = Failure::MaxInflight;
        else if (item.frame.size > options_.max_send_bytes - connection.send_bytes) failure = Failure::SendLimit;
        if (failure != Failure::None) {
            item.state = State::NotStarted;
            item.failure = failure;
            return false;
        }
        item.state = State::Queued;
        ++inflight_;
        inflight_high_water_ = std::max(inflight_high_water_, inflight_);
        connection.pending.push(index);
        connection.outgoing.push(index);
        connection.send_bytes += item.frame.size;
        connection.send_high_water = std::max(connection.send_high_water, connection.send_bytes);
        if (!connection.writing) write(item.command.client - 1);
        return true;
    }

    void write(std::size_t index) {
        auto& connection = *connections_[index];
        const auto item_index = connection.outgoing.front();
        auto& item = items_[item_index];
        connection.writing = true;
        item.first_attempt = now_ns();
        item.state = State::Started;
        const auto bytes = item.frame.bytes();
        asio::async_write(connection.socket, asio::buffer(bytes.data(), bytes.size()),
            [this, index, item_index](const ErrorCode& error, std::size_t) {
                auto& current = *connections_[index];
                if (finished_ || !current.connected) return;
                if (error) return fail_connection(index, Failure::Write, "write: " + error.message());
                auto& completed = items_[item_index];
                completed.write_completed = now_ns();
                current.send_bytes -= completed.frame.size;
                current.outgoing.pop();
                current.writing = false;
                if (!current.outgoing.empty()) write(index);
                maybe_finish();
            });
    }

    void next_setup() {
        deadline_.cancel();
        if (setup_next_ == setup_count_) return begin_measurement();
        if (!arm_deadline(Failure::Setup)) return;
        if (!enqueue(setup_next_)) finish(Failure::Setup, "setup could not be started within configured limits");
    }

    void begin_measurement() {
        started_ = now_ns();
        const auto maximum = static_cast<Ns>(std::numeric_limits<std::int64_t>::max());
        const auto last = offsets_.empty() ? 0 : offsets_.back();
        const auto drain = options_.drain_ms * 1000000;
        if (last > maximum - started_ || drain > maximum - started_ - last) {
            started_ = 0;
            return finish(Failure::Startup, "schedule exceeds representable steady_clock time");
        }
        // Offsets were prepared before startup; do no plan-sized work after this clock anchor.
        deadline_.expires_at(at_ns(started_ + last + drain));
        deadline_.async_wait([this](const ErrorCode& error) { if (!error) finish(Failure::Deadline, "drain deadline exceeded"); });
        schedule();
    }

    void schedule() {
        if (finished_) return;
        const auto now = now_ns();
        std::size_t budget = 256;
        while (next_ < offsets_.size() && started_ + offsets_[next_] <= now && budget != 0) {
            (void)enqueue(setup_count_ + next_);
            ++next_;
            --budget;
        }
        if (next_ == offsets_.size()) return maybe_finish();
        schedule_timer_.expires_at(at_ns(started_ + offsets_[next_]));
        schedule_timer_.async_wait([this](const ErrorCode& error) { if (!error) schedule(); });
    }

    void maybe_finish() {
        if (started_ == 0 || next_ != offsets_.size() || inflight_ != 0) return;
        for (const auto& connection : connections_) if (!connection->outgoing.empty()) return;
        finish(Failure::None, failure_);
    }

    Counts count(std::size_t begin, std::size_t end) const {
        Counts result;
        result.planned = end - begin;
        for (std::size_t i = begin; i < end; ++i) {
            const auto& item = items_[i];
            if (item.first_attempt != 0) ++result.started;
            else ++result.not_started;
            if (item.state == State::Completed) {
                ++result.completed;
                if (item.completion == CompletionStatus::Accepted) ++result.accepted;
                if (item.completion == CompletionStatus::Rejected) ++result.rejected;
            } else if (item.state == State::Failed) ++result.failed;
            else if (item.first_attempt != 0) ++result.unfinished;
        }
        return result;
    }

    void csv(const std::filesystem::path& path, std::size_t begin, std::size_t end) const {
        std::ofstream out(path);
        out << "idx,logical,actual,request,scheduled_ns,first_attempt_ns,write_completed_ns,complete_ns,command_seq,events,trades,checksum,completion_status,outcome,failure,send_lag_ns,rtt_ns,offset_ns\n";
        const auto optional = [&](Ns value) { if (value != 0) out << value; out << ','; };
        for (std::size_t i = begin; i < end; ++i) {
            const auto& item = items_[i];
            out << i - begin << ',' << item.command.client << ',' << connections_[item.command.client - 1]->actual << ',' << item.command.request << ',';
            const auto scheduled = started_ != 0 && i >= setup_count_ ? started_ + offsets_[i - setup_count_] : 0;
            optional(scheduled); optional(item.first_attempt); optional(item.write_completed); optional(item.complete);
            out << item.command_seq << ',' << item.events << ',' << item.trades << ',' << item.checksum << ','
                << static_cast<unsigned>(item.completion) << ',' << outcome(item.state) << ',' << failure_name(item.failure) << ',';
            if (item.first_attempt != 0 && scheduled != 0) out << item.first_attempt - scheduled;
            out << ',';
            if (item.complete != 0) out << item.complete - item.first_attempt;
            out << ',';
            if (i >= setup_count_) out << offsets_[i - setup_count_];
            out << '\n';
        }
        if (!out) throw std::runtime_error("cannot write " + path.string());
    }

    static void counts_json(std::ostream& out, const Counts& c) {
        out << "\"planned\":" << c.planned << ",\"not_started\":" << c.not_started << ",\"started\":" << c.started
            << ",\"completed\":" << c.completed << ",\"failed\":" << c.failed << ",\"unfinished\":" << c.unfinished
            << ",\"accepted\":" << c.accepted << ",\"rejected\":" << c.rejected;
    }

    void write_evidence() const {
        std::filesystem::create_directories(options_.output);
        csv(options_.output / "client_samples.csv", setup_count_, items_.size());
        csv(options_.output / "setup_samples.csv", 0, setup_count_);
        std::ofstream out(options_.output / "client.json");
        out << "{\"schema_version\":1,\"exit_status\":" << exit_code_ << ",\"failure\":" << json(failure_) << ',';
        const auto result = count(setup_count_, items_.size());
        counts_json(out, result);
        out << ",\"setup\":{"; counts_json(out, count(0, setup_count_));
        out << "},\"measurement_start_ns\":" << started_ << ",\"measurement_end_ns\":" << ended_
            << ",\"input_hash\":" << json(input_hash_) << ",\"setup_hash\":" << json(setup_hash_)
            << ",\"schedule_hash\":" << json(schedule_hash_) << ",\"hash_algorithm\":\"fnv1a64\""
            << ",\"tcp_nodelay\":true"
            << ",\"max_inflight\":" << options_.max_inflight << ",\"max_send_bytes\":" << options_.max_send_bytes
            << ",\"drain_ms\":" << options_.drain_ms << ",\"inflight_high_water\":" << inflight_high_water_
            << ",\"bbo_received\":" << bbo_received_ << ",\"maker_trades_received\":" << maker_trades_
            << ",\"clock_probe\":{\"clock\":\"steady_clock\",\"samples\":" << probe_count_
            << ",\"min_positive_interval_ns\":" << min_interval_ << ",\"recording_elapsed_ns\":" << recording_ns_
            << ",\"probe_sink\":" << probe_sink_ << "},\"logical_to_actual\":[";
        for (std::size_t i = 0; i < connections_.size(); ++i) {
            if (i != 0) out << ',';
            out << "{\"logical\":" << i + 1 << ",\"actual\":" << connections_[i]->actual
                << ",\"send_high_water\":" << connections_[i]->send_high_water << '}';
        }
        out << "]}\n";
        if (!out) throw std::runtime_error("cannot write client.json");
        std::cout << "planned=" << result.planned << " started=" << result.started << " completed=" << result.completed
            << " not_started=" << result.not_started << " failed=" << result.failed << " unfinished=" << result.unfinished << '\n';
    }

    Options options_;
    asio::io_context io_;
    Tcp::resolver resolver_;
    asio::steady_timer schedule_timer_, deadline_;
    std::vector<Item> items_;
    std::vector<Ns> offsets_;
    std::vector<std::unique_ptr<Connection>> connections_;
    std::size_t setup_count_{}, setup_next_{}, ready_{}, next_{}, inflight_{}, inflight_high_water_{};
    Ns started_{}, ended_{}, bbo_received_{}, maker_trades_{};
    static constexpr std::size_t probe_count_ = 10000;
    Ns min_interval_{}, recording_ns_{}, probe_sink_{};
    std::string input_hash_, setup_hash_, schedule_hash_, failure_;
    bool finished_{};
    int exit_code_{};
};
} // namespace

int main(int argc, char** argv) {
    try {
        Options options;
        for (int i = 1; i < argc; ++i) {
            const std::string_view option(argv[i]);
            if (option == "--help") {
                std::cout << "loadgen --setup FILE --input FILE --schedule FILE --output-dir DIR\n"
                    "  [--host 127.0.0.1] [--port 19999] [--connections 1]\n"
                    "  [--max-inflight 16384] [--max-send-bytes 65536] [--drain-ms 5000]\n";
                return 0;
            }
            if (i + 1 == argc) throw std::invalid_argument("missing option value");
            const std::string_view value(argv[++i]);
            if (option == "--host") options.host = value;
            else if (option == "--port") { options.port = value; if (number<std::uint16_t>(value) == 0) throw std::invalid_argument("port must be nonzero"); }
            else if (option == "--connections") options.connections = number<std::size_t>(value);
            else if (option == "--max-inflight") options.max_inflight = number<std::size_t>(value);
            else if (option == "--max-send-bytes") options.max_send_bytes = number<std::size_t>(value);
            else if (option == "--drain-ms") options.drain_ms = number<Ns>(value);
            else if (option == "--setup") options.setup = value;
            else if (option == "--input") options.input = value;
            else if (option == "--schedule") options.schedule = value;
            else if (option == "--output-dir") options.output = value;
            else throw std::invalid_argument("unknown option: " + std::string(option));
        }
        if (options.connections == 0 || options.connections > std::numeric_limits<ClientId>::max() ||
            options.max_inflight == 0 || options.max_inflight == std::numeric_limits<std::size_t>::max() ||
            options.max_send_bytes == 0 || options.drain_ms == 0 ||
            options.drain_ms > static_cast<Ns>(std::numeric_limits<std::int64_t>::max()) / 1000000)
            throw std::invalid_argument("limits must be positive and representable");
        if (options.setup.empty() || options.input.empty() || options.schedule.empty() || options.output.empty())
            throw std::invalid_argument("--setup, --input, --schedule and --output-dir are required");
        return Loadgen(std::move(options)).run();
    } catch (const std::exception& error) {
        std::cerr << "loadgen: " << error.what() << '\n';
        return 1;
    }
}
