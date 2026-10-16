#include "llmatch/server.hpp"

#include <algorithm>
#include <csignal>
#include <cstring>
#include <limits>
#include <stdexcept>

namespace llmatch {
namespace asio = boost::asio;
using boost::system::error_code;
namespace {
ServerConfig checked_config(ServerConfig config) {
    if (config.max_connections == 0 || config.send_limit < protocol::max_frame_size ||
        config.shutdown_timeout.count() <= 0 || config.socket_send_buffer < 0) {
        throw std::invalid_argument("invalid connection/send/shutdown configuration");
    }
    return config;
}
}

const char* close_reason_name(CloseReason reason) {
    switch (reason) {
    case CloseReason::PeerEof: return "peer_eof";
    case CloseReason::ReadError: return "read_error";
    case CloseReason::WriteError: return "write_error";
    case CloseReason::Protocol: return "protocol_error";
    case CloseReason::TruncatedFrame: return "truncated_frame";
    case CloseReason::SlowClient: return "slow_client";
    case CloseReason::Shutdown: return "shutdown";
    case CloseReason::Count: break;
    }
    return "unknown";
}

struct MatchingServer::Connection : std::enable_shared_from_this<Connection> {
    struct Outgoing { protocol::Frame frame; bool business{}; };
    MatchingServer& server;
    Tcp::socket socket;
    ClientId id;
    std::array<std::uint8_t, 4096> receive{};
    std::size_t used{};
    bool reading{};
    bool writing{};
    bool closed{};
    std::optional<Command> pending;
    std::uint64_t pending_ready_ns{};
    std::deque<Outgoing> outgoing;
    std::size_t outgoing_bytes{};

    Connection(MatchingServer& owner, Tcp::socket stream, ClientId client)
        : server(owner), socket(std::move(stream)), id(client) {}

    void start() {
        socket.set_option(Tcp::no_delay(true));
        if (server.config_.socket_send_buffer) {
            socket.set_option(asio::socket_base::send_buffer_size(server.config_.socket_send_buffer));
        }
        enqueue(protocol::encode(protocol::Welcome{id}), false);
        enqueue(protocol::encode(server.cached_bbo_), false);
        read();
    }

    void close(CloseReason reason) {
        if (closed) return;
        closed = true;
        ++server.stats_.closes[static_cast<std::size_t>(reason)];
        server.stats_.discarded_frames += outgoing.size();
        for (const auto& item : outgoing) server.stats_.discarded_business_frames += item.business;
        error_code ignored;
        socket.close(ignored);
        pending.reset();
        server.connections_.erase(id);
        // Keep the in-flight buffer alive until its cancellation callback runs.
        if (!writing) { outgoing.clear(); outgoing_bytes = 0; }
    }

    void enqueue(const protocol::Frame& frame, bool business) {
        if (closed) return;
        if (frame.size > server.config_.send_limit - outgoing_bytes) {
            if (business) ++server.stats_.discarded_business_frames;
            ++server.stats_.discarded_frames;
            close(CloseReason::SlowClient);
            return;
        }
        outgoing.push_back({frame, business});
        outgoing_bytes += frame.size;
        server.stats_.send_high_water = std::max(server.stats_.send_high_water, outgoing_bytes);
        if (!writing) write();
    }

    void write() {
        if (closed || outgoing.empty()) return;
        writing = true;
        const auto& frame = outgoing.front().frame;
        asio::async_write(socket, asio::buffer(frame.storage.data(), frame.size),
            [self = shared_from_this()](error_code error, std::size_t) {
                self->writing = false;
                if (self->closed) {
                    self->outgoing.clear();
                    self->outgoing_bytes = 0;
                    self->server.maybe_finish();
                    return;
                }
                if (error) {
                    self->close(CloseReason::WriteError);
                } else {
                    auto& owner = self->server;
                    ++owner.stats_.written_frames;
                    owner.stats_.written_business_frames += self->outgoing.front().business;
                    self->outgoing_bytes -= self->outgoing.front().frame.size;
                    self->outgoing.pop_front();
                    self->write();
                }
                self->server.maybe_finish();
            });
    }

    void read() {
        if (closed || reading || pending || server.draining_) return;
        reading = true;
        socket.async_read_some(asio::buffer(receive.data() + used, receive.size() - used),
            [self = shared_from_this()](error_code error, std::size_t count) {
                self->reading = false;
                if (self->closed || self->server.draining_) return;
                if (error) {
                    const auto reason = error == asio::error::eof
                        ? (self->used ? CloseReason::TruncatedFrame : CloseReason::PeerEof)
                        : CloseReason::ReadError;
                    self->close(reason);
                    return;
                }
                self->used += count;
                self->process_input();
            });
    }

    bool runnable() const {
        if (closed || reading || server.draining_) return false;
        if (pending) return server.pipeline_->has_command_space();
        return used && protocol::inspect({receive.data(), used}).status != protocol::FrameStatus::NeedMore;
    }

    void process_input() {
        if (closed || reading || server.draining_) return;
        for (unsigned budget = 0; budget < 16; ++budget) {
            if (pending) {
                switch (server.pipeline_->try_submit(*pending, pending_ready_ns)) {
                case SubmitResult::Full: return;
                case SubmitResult::Stopping: return;
                case SubmitResult::RecordLimit:
                    server.begin_shutdown("experiment record capacity exhausted");
                    return;
                case SubmitResult::Admitted: pending.reset(); break;
                }
            }
            const auto info = protocol::inspect({receive.data(), used});
            if (info.status == protocol::FrameStatus::Invalid ||
                (info.status == protocol::FrameStatus::Ready && !protocol::is_request(info.type))) {
                close(CloseReason::Protocol);
                return;
            }
            if (info.status == protocol::FrameStatus::NeedMore) { read(); return; }
            pending_ready_ns = steady_now_ns();
            pending = protocol::decode_request({receive.data(), info.frame_size}, id);
            used -= info.frame_size;
            std::memmove(receive.data(), receive.data() + info.frame_size, used);
        }
        server.schedule_pump(); // Continue bounded parsing, without an overlapping read.
    }
};

MatchingServer::MatchingServer(ServerConfig config)
    : config_(checked_config(std::move(config))), work_(asio::make_work_guard(io_)),
      acceptor_(io_), signals_(io_, SIGINT, SIGTERM), shutdown_timer_(io_) {
    const Tcp::endpoint endpoint(asio::ip::make_address(config_.address), config_.port);
    acceptor_.open(endpoint.protocol());
    acceptor_.set_option(Tcp::acceptor::reuse_address(true));
    acceptor_.bind(endpoint);
    acceptor_.listen();
    pump_clients_.reserve(config_.max_connections);
    pipeline_ = std::make_unique<MatchingPipeline>(config_.pipeline, [this] { schedule_pump(); });
}

MatchingServer::~MatchingServer() {
    if (pipeline_) { pipeline_->request_abort(); pipeline_->join(); }
}

std::uint16_t MatchingServer::port() const { return acceptor_.local_endpoint().port(); }

int MatchingServer::run() {
    accept_next();
    signals_.async_wait([this](error_code error, int) { if (!error) begin_shutdown(); });
    try {
        io_.run();
    } catch (const std::exception& error) {
        failure_ = error.what();
        pipeline_->request_abort();
    }
    pipeline_->join();
    if (!pipeline_->failure().empty()) failure_ = pipeline_->failure();
    if (pipeline_->stats().completed != pipeline_->admitted() && failure_.empty()) {
        failure_ = "admitted commands were not completely drained";
    }
    return failure_.empty() ? 0 : 1;
}

void MatchingServer::accept_next() {
    acceptor_.async_accept([this](error_code error, Tcp::socket socket) {
        if (draining_) return;
        if (error) { begin_shutdown("accept failed: " + error.message()); return; }
        if (connections_.size() == config_.max_connections) {
            ++stats_.connection_limit_rejections;
            error_code ignored;
            socket.close(ignored);
        } else if (next_client_ == std::numeric_limits<ClientId>::max()) {
            begin_shutdown("client identity space exhausted");
        } else {
            const auto id = next_client_++;
            auto connection = std::make_shared<Connection>(*this, std::move(socket), id);
            connections_.emplace(id, connection);
            ++stats_.connections;
            connection->start();
        }
        if (!draining_) accept_next();
    });
}

void MatchingServer::schedule_pump() {
    if (!pump_scheduled_.exchange(true, std::memory_order_acq_rel)) {
        asio::post(io_, [this] { pump(); });
    }
}

bool MatchingServer::runnable_input() const {
    return std::any_of(connections_.begin(), connections_.end(),
        [](const auto& item) { return item.second->runnable(); });
}

void MatchingServer::pump() {
    if (!finished_) {
        ServiceMessage message;
        for (unsigned budget = 0; budget < 128 && pipeline_->try_pop(message); ++budget) route(message);
        if (!draining_) {
            pump_clients_.clear();
            for (const auto& [id, connection] : connections_) {
                (void)connection;
                pump_clients_.push_back(id);
            }
            const auto count = pump_clients_.size();
            for (std::size_t i = 0; i < count; ++i) {
                const auto id = pump_clients_[(round_robin_ + i) % count];
                if (const auto found = connections_.find(id); found != connections_.end()) {
                    // process_input may erase the connection; retain its lifetime.
                    auto connection = found->second;
                    connection->process_input();
                }
            }
            if (count) round_robin_ = (round_robin_ + 1) % count;
        }
        if (pipeline_->done() && !draining_) begin_shutdown("matching worker exited unexpectedly");
        maybe_finish();
    }
    rearm_pump();
}

void MatchingServer::rearm_pump() {
    // A producer racing the reset either observes false and posts, or its
    // output/termination is found by this recheck. A done notification can
    // arrive with an empty queue, so checking output alone loses shutdown.
    pump_scheduled_.store(false, std::memory_order_release);
    if (!finished_) {
        if (pipeline_->done() && !draining_) begin_shutdown("matching worker exited unexpectedly");
        maybe_finish();
        if (!finished_ && (pipeline_->has_output() || runnable_input())) schedule_pump();
    }
}

void MatchingServer::send_to(ClientId client, const protocol::Frame& frame) {
    const auto found = connections_.find(client);
    if (found == connections_.end()) { ++stats_.missing_business_recipients; return; }
    auto connection = found->second;
    connection->enqueue(frame, true);
}

void MatchingServer::route(const ServiceMessage& message) {
    if (const auto* event = std::get_if<Event>(&message)) {
        ++stats_.consumed_events;
        const auto frame = protocol::encode(*event);
        if (event->kind == EventKind::Trade) {
            send_to(event->maker_client, frame);
            if (event->taker_client != event->maker_client) send_to(event->taker_client, frame);
        } else {
            send_to(event->client, frame);
        }
    } else {
        ++stats_.consumed_bbo;
        cached_bbo_ = std::get<Bbo>(message);
        const auto frame = protocol::encode(cached_bbo_);
        for (auto at = connections_.begin(); at != connections_.end();) {
            auto connection = (at++)->second;
            connection->enqueue(frame, false);
        }
    }
}

void MatchingServer::begin_shutdown(const std::string& failure) {
    if (!failure.empty() && failure_.empty()) failure_ = failure;
    if (draining_) return;
    draining_ = true;
    error_code ignored;
    acceptor_.close(ignored);
    signals_.cancel(ignored);
    pipeline_->request_drain();
    shutdown_timer_.expires_after(config_.shutdown_timeout);
    shutdown_timer_.async_wait([this](error_code error) { if (!error) finish(true); });
    schedule_pump();
}

void MatchingServer::maybe_finish() {
    if (!draining_ || finished_ || !pipeline_->done() || pipeline_->has_output()) return;
    const bool writes_pending = std::any_of(connections_.begin(), connections_.end(),
        [](const auto& item) { return !item.second->outgoing.empty(); });
    if (!writes_pending) finish(false);
}

void MatchingServer::finish(bool timed_out) {
    if (finished_) return;
    finished_ = true;
    if (timed_out) {
        failure_ = "shutdown deadline exhausted";
        pipeline_->request_abort();
    }
    error_code ignored;
    shutdown_timer_.cancel();
    signals_.cancel(ignored);
    acceptor_.close(ignored);
    while (!connections_.empty()) {
        auto connection = connections_.begin()->second;
        connection->close(CloseReason::Shutdown);
    }
    work_.reset();
}

} // namespace llmatch
