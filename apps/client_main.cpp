#include "llmatch/protocol.hpp"

#include <boost/asio.hpp>
#include <algorithm>
#include <array>
#include <charconv>
#include <chrono>
#include <cstring>
#include <deque>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <unistd.h>

namespace {
using namespace llmatch;
namespace asio = boost::asio;
using Tcp = asio::ip::tcp;
using ErrorCode = boost::system::error_code;
constexpr std::size_t max_line = 4096;
constexpr std::size_t max_pending = 1024;
constexpr std::size_t max_send_bytes = 64 * 1024;
constexpr auto finish_timeout = std::chrono::seconds(5);

template<class T> T integer(std::string_view text) {
    T value{};
    const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), value);
    if (error != std::errc{} || end != text.data() + text.size())
        throw std::invalid_argument("invalid integer: " + std::string(text));
    return value;
}

std::optional<Command> parse(std::string_view line, ClientId client) {
    std::istringstream input{std::string(line)};
    std::array<std::string, 7> fields;
    std::size_t count = 0;
    while (count < fields.size() && input >> fields[count]) ++count;
    if (count == 0) return std::nullopt;
    if (fields[0] == "quit" && count == 1) return std::nullopt;
    if (fields[0] == "cancel" && count == 3)
        return Command{client, integer<RequestId>(fields[1]), CancelOrder{integer<OrderId>(fields[2])}};
    if ((fields[0] == "limit" && count == 6) || (fields[0] == "market" && count == 5)) {
        if (fields[3] != "buy" && fields[3] != "sell")
            throw std::invalid_argument("side must be buy or sell");
        const Side side = fields[3] == "buy" ? Side::Buy : Side::Sell;
        const auto request = integer<RequestId>(fields[1]);
        const auto id = integer<OrderId>(fields[2]);
        if (fields[0] == "limit")
            return Command{client, request, LimitOrder{id, side, integer<Price>(fields[4]), integer<Quantity>(fields[5])}};
        return Command{client, request, MarketOrder{id, side, integer<Quantity>(fields[4])}};
    }
    throw std::invalid_argument("expected limit REQUEST ORDER buy|sell PRICE QTY, market REQUEST ORDER buy|sell QTY, cancel REQUEST ORDER, or quit");
}

void print_event(const Event& e) {
    constexpr std::array kinds{"Accepted", "Rejected", "Trade", "Rested", "Cancelled", "CommandComplete"};
    constexpr std::array commands{"Limit", "Market", "Cancel"};
    constexpr std::array rejects{"None", "InvalidClientId", "InvalidRequestId", "InvalidOrderId", "InvalidSide",
        "InvalidQuantity", "InvalidPrice", "DuplicateOrder", "UnknownOrder", "NotOwner", "CapacityExceeded"};
    constexpr std::array cancels{"None", "UserCancel", "IocRemainder"};
    constexpr std::array completions{"None", "Accepted", "Rejected"};
    std::cout << "{\"type\":\"event\",\"kind\":\"" << kinds[static_cast<std::size_t>(e.kind)]
        << "\",\"command_kind\":\"" << commands[static_cast<std::size_t>(e.command_kind)]
        << "\",\"command_seq\":" << e.command_seq << ",\"event_seq\":" << e.event_seq
        << ",\"client\":" << e.client << ",\"request\":" << e.request << ",\"order_id\":" << e.order_id
        << ",\"reject_reason\":\"" << rejects[static_cast<std::size_t>(e.reject_reason)]
        << "\",\"cancel_reason\":\"" << cancels[static_cast<std::size_t>(e.cancel_reason)]
        << "\",\"completion\":\"" << completions[static_cast<std::size_t>(e.completion)]
        << "\",\"side\":\"" << (e.side == Side::Buy ? "buy" : "sell")
        << "\",\"price\":" << e.price << ",\"qty\":" << e.qty << ",\"arrival_seq\":" << e.arrival_seq
        << ",\"maker_id\":" << e.maker_id << ",\"taker_id\":" << e.taker_id
        << ",\"maker_client\":" << e.maker_client << ",\"taker_client\":" << e.taker_client
        << ",\"maker_arrival_seq\":" << e.maker_arrival_seq << ",\"taker_arrival_seq\":" << e.taker_arrival_seq
        << ",\"filled_qty\":" << e.filled_qty << ",\"resting_qty\":" << e.resting_qty
        << ",\"cancelled_qty\":" << e.cancelled_qty << "}" << std::endl;
}

void print_bbo(const Bbo& bbo) {
    std::cout << "{\"type\":\"bbo\",\"bid_present\":" << (bbo.bid_present ? "true" : "false")
        << ",\"ask_present\":" << (bbo.ask_present ? "true" : "false")
        << ",\"bid_price\":" << bbo.bid_price << ",\"bid_qty\":" << bbo.bid_qty
        << ",\"ask_price\":" << bbo.ask_price << ",\"ask_qty\":" << bbo.ask_qty
        << ",\"command_seq\":" << bbo.command_seq << ",\"as_of_event_seq\":" << bbo.as_of_event_seq
        << "}" << std::endl;
}

class Client {
public:
    Client(std::string host, std::string port)
        : resolver_(io_), socket_(io_), input_(io_, ::dup(STDIN_FILENO)), deadline_(io_) {
        deadline_.expires_after(finish_timeout);
        deadline_.async_wait([this](const ErrorCode& error) {
            if (!error) finish(1, "connection or Welcome deadline exceeded");
        });
        resolver_.async_resolve(host, port, [this](const ErrorCode& error, const Tcp::resolver::results_type& endpoints) {
            if (finished_) return;
            if (error) return finish(1, "resolve: " + error.message());
            asio::async_connect(socket_, endpoints, [this](const ErrorCode& connect_error, const Tcp::endpoint&) {
                if (finished_) return;
                if (connect_error) return finish(1, "connect: " + connect_error.message());
                ErrorCode option_error;
                socket_.set_option(Tcp::no_delay(true), option_error);
                if (option_error) return finish(1, "TCP_NODELAY: " + option_error.message());
                read_network();
            });
        });
    }

    int run() { io_.run(); return exit_code_; }

private:
    struct Pending { RequestId request; OrderId order; CommandKind kind; Sequence sequence{}; };

    void finish(int code, const std::string& reason = {}) {
        if (finished_) return;
        finished_ = true;
        exit_code_ = code;
        if (!reason.empty()) std::cerr << reason << "; pending=" << pending_.size() << '\n';
        std::cout << "{\"type\":\"client_summary\",\"submitted\":" << submitted_
            << ",\"completed\":" << completed_ << ",\"pending\":" << pending_.size() << "}" << std::endl;
        ErrorCode ignored;
        resolver_.cancel();
        deadline_.cancel();
        input_.close(ignored);
        socket_.close(ignored);
    }

    void maybe_finish() {
        if (draining_ && pending_.empty() && outgoing_.empty()) finish(0);
    }

    void arm_completion_deadline() {
        deadline_.expires_after(finish_timeout);
        deadline_.async_wait([this](const ErrorCode& error) {
            if (!error) finish(1, "Complete deadline exceeded");
        });
    }

    void drain() {
        if (draining_ || finished_) return;
        draining_ = true;
        ErrorCode ignored;
        input_.close(ignored);
        arm_completion_deadline();
        maybe_finish();
    }

    void read_network() {
        socket_.async_read_some(asio::buffer(received_.data() + received_size_, received_.size() - received_size_),
            [this](const ErrorCode& error, std::size_t count) {
                if (finished_) return;
                if (error) {
                    if (received_size_ != 0) return finish(1, "truncated server frame: " + error.message());
                    return finish(client_ != 0 && pending_.empty() ? 0 : 1, "server disconnected: " + error.message());
                }
                received_size_ += count;
                std::size_t consumed = 0;
                try {
                    while (consumed < received_size_ && !finished_) {
                        const auto bytes = std::span(received_).subspan(consumed, received_size_ - consumed);
                        const auto info = protocol::inspect(bytes);
                        if (info.status == protocol::FrameStatus::Invalid) throw protocol::ProtocolError(info.error);
                        if (info.status == protocol::FrameStatus::NeedMore) break;
                        receive(protocol::decode(bytes.first(info.frame_size)));
                        consumed += info.frame_size;
                    }
                } catch (const std::exception& exception) {
                    return finish(1, "server protocol: " + std::string(exception.what()));
                }
                if (finished_) return;
                received_size_ -= consumed;
                std::memmove(received_.data(), received_.data() + consumed, received_size_);
                read_network();
            });
    }

    void receive(const protocol::Decoded& message) {
        if (const auto* welcome = std::get_if<protocol::Welcome>(&message)) {
            if (client_ != 0 || welcome->client == 0) throw std::runtime_error("invalid Welcome");
            client_ = welcome->client;
            deadline_.cancel();
            std::cout << "{\"type\":\"welcome\",\"client\":" << client_ << ",\"version\":" << protocol::version << "}" << std::endl;
            read_input();
        } else if (client_ == 0) {
            throw std::runtime_error("expected Welcome first");
        } else if (const auto* bbo = std::get_if<Bbo>(&message)) {
            print_bbo(*bbo);
        } else if (const auto* event = std::get_if<Event>(&message)) {
            receive_event(*event);
        } else {
            throw std::runtime_error("server sent a request frame");
        }
    }

    void receive_event(const Event& event) {
        print_event(event);
        if (event.kind == EventKind::Accepted || event.kind == EventKind::Rejected || event.kind == EventKind::CommandComplete) {
            if (pending_.empty()) throw std::runtime_error("result without a pending request");
            auto& pending = pending_.front();
            if (event.client != client_ || event.request != pending.request || event.order_id != pending.order || event.command_kind != pending.kind)
                throw std::runtime_error("result does not match the first pending request");
            if (event.kind == EventKind::CommandComplete) {
                if (pending.sequence == 0 || pending.sequence != event.command_seq)
                    throw std::runtime_error("Complete without its correlated Accepted/Rejected");
                pending_.pop_front();
                ++completed_;
                if (!draining_) {
                    if (pending_.empty()) deadline_.cancel();
                    else arm_completion_deadline();
                }
                read_input();
                maybe_finish();
            } else {
                if (pending.sequence != 0 || event.command_seq == 0)
                    throw std::runtime_error("duplicate or invalid request acknowledgement");
                pending.sequence = event.command_seq;
            }
        }
        // Maker Trade belongs to the active taker request. It is printed but
        // never acknowledges or completes this connection's pending request.
    }

    void read_input() {
        if (finished_ || draining_ || input_active_ || pending_.size() == max_pending) return;
        input_active_ = true;
        asio::async_read_until(input_, asio::dynamic_buffer(input_buffer_, max_line), '\n',
            [this](const ErrorCode& error, std::size_t count) {
                input_active_ = false;
                if (finished_ || draining_) return;
                if (error == asio::error::eof) {
                    if (!input_buffer_.empty()) accept_line(input_buffer_);
                    return drain();
                }
                if (error) return finish(1, "stdin (maximum line 4096 bytes): " + error.message());
                const auto line = input_buffer_.substr(0, count);
                input_buffer_.erase(0, count);
                accept_line(line);
                read_input();
            });
    }

    void accept_line(std::string_view line) {
        std::istringstream words{std::string(line)};
        std::string first, extra;
        words >> first;
        if (first == "quit" && !(words >> extra)) return drain();
        try {
            const auto command = parse(line, client_);
            if (!command) return;
            auto frame = protocol::encode(*command);
            if (send_bytes_ + frame.size > max_send_bytes) return finish(1, "send buffer limit exceeded");
            pending_.push_back({command->request, order_id(*command), command_kind(*command)});
            // Progress also has a deadline while stdin is paused at max_pending:
            // EOF or quit may still be waiting behind that input backpressure.
            if (pending_.size() == 1) arm_completion_deadline();
            ++submitted_;
            send_bytes_ += frame.size;
            outgoing_.push_back(std::move(frame));
            if (outgoing_.size() == 1) write_next();
        } catch (const std::invalid_argument& error) {
            std::cerr << "input: " << error.what() << '\n';
        }
    }

    void write_next() {
        const auto bytes = outgoing_.front().bytes();
        asio::async_write(socket_, asio::buffer(bytes.data(), bytes.size()),
            [this](const ErrorCode& error, std::size_t) {
                if (finished_) return;
                if (error) return finish(1, "write: " + error.message());
                send_bytes_ -= outgoing_.front().size;
                outgoing_.pop_front();
                if (!outgoing_.empty()) write_next();
                maybe_finish();
            });
    }

    asio::io_context io_;
    Tcp::resolver resolver_;
    Tcp::socket socket_;
    asio::posix::stream_descriptor input_;
    asio::steady_timer deadline_;
    std::array<std::uint8_t, 4096> received_{};
    std::size_t received_size_{};
    std::string input_buffer_;
    std::deque<protocol::Frame> outgoing_;
    std::deque<Pending> pending_;
    std::size_t send_bytes_{};
    std::uint64_t submitted_{};
    std::uint64_t completed_{};
    ClientId client_{};
    bool input_active_{};
    bool draining_{};
    bool finished_{};
    int exit_code_{};
};
} // namespace

int main(int argc, char** argv) {
    try {
        std::string host = "127.0.0.1", port = "19999";
        for (int i = 1; i < argc; ++i) {
            const std::string_view option(argv[i]);
            if (option == "--help") {
                std::cout << "matching_client [--host HOST] [--port PORT]\n"
                    "limit REQUEST ORDER buy|sell PRICE QTY\nmarket REQUEST ORDER buy|sell QTY\ncancel REQUEST ORDER\nquit\n";
                return 0;
            }
            if ((option != "--host" && option != "--port") || i + 1 == argc)
                throw std::invalid_argument("expected --host HOST or --port PORT");
            if (option == "--host") host = argv[++i];
            else {
                port = argv[++i];
                if (integer<std::uint16_t>(port) == 0) throw std::invalid_argument("port must be 1..65535");
            }
        }
        return Client(std::move(host), std::move(port)).run();
    } catch (const std::exception& error) {
        std::cerr << "matching_client: " << error.what() << '\n';
        return 1;
    }
}
