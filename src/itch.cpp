#include "llmatch/itch.hpp"

#include <algorithm>
#include <cassert>
#include <iomanip>
#include <limits>
#include <sstream>
#include <utility>

namespace llmatch::itch {
namespace {
constexpr std::uint64_t day_ns = 86'400'000'000'000ULL;
constexpr std::uint32_t maximum_price = 2'000'000'000;

std::string type_text(char type) {
    const auto byte = static_cast<unsigned char>(type);
    if (byte >= 32 && byte <= 126) return std::string(1, type);
    std::ostringstream out;
    out << "0x" << std::hex << std::setw(2) << std::setfill('0') << static_cast<unsigned>(byte);
    return out.str();
}

std::uint64_t integer(std::span<const std::uint8_t> bytes, std::size_t offset, std::size_t size) {
    std::uint64_t result = 0;
    for (std::size_t i = 0; i < size; ++i) result = (result << 8U) | bytes[offset + i];
    return result;
}

std::string alpha(std::span<const std::uint8_t> bytes, std::size_t offset, std::size_t size) {
    std::string result(reinterpret_cast<const char*>(bytes.data() + offset), size);
    while (!result.empty() && result.back() == ' ') result.pop_back();
    return result;
}

bool printable_ascii(const std::string& value) {
    return std::all_of(value.begin(), value.end(), [](unsigned char c) { return c >= 32 && c <= 126; });
}

[[noreturn]] void fail(const Message& message, const std::string& reason) {
    const bool order_message = std::string("AFECXDU").find(message.type) != std::string::npos;
    throw Error(reason, message.offset, message.message_index, message.type,
                order_message ? std::optional(message.reference) : std::nullopt);
}

void require(bool condition, const Message& message, const std::string& reason) {
    if (!condition) fail(message, reason);
}
} // namespace

Error::Error(std::string reason, std::uint64_t byte_offset, std::uint64_t index,
             char message_type, std::optional<std::uint64_t> order_reference)
    : std::runtime_error("offset=" + std::to_string(byte_offset) + " message_index=" + std::to_string(index) +
                         " type=" + type_text(message_type) +
                         (order_reference ? " reference=" + std::to_string(*order_reference) : "") + " " + reason),
      offset(byte_offset), message_index(index), type(message_type), reference(order_reference) {}

std::string Error::type_label() const { return type_text(type); }

std::size_t payload_size(char type) {
    switch (type) {
    case 'S': return 12; case 'R': return 39; case 'A': return 36; case 'F': return 40;
    case 'E': return 31; case 'C': return 36; case 'X': return 23; case 'D': return 19; case 'U': return 35;
    case 'H': return 25; case 'Y': return 20; case 'L': return 26; case 'V': return 35;
    case 'W': return 12; case 'K': return 28; case 'J': return 35; case 'h': return 21;
    case 'P': return 44; case 'Q': return 40; case 'B': return 19; case 'I': return 50;
    case 'N': return 20; case 'O': return 48;
    default: return 0;
    }
}

Message decode(std::span<const std::uint8_t> bytes, std::uint64_t offset, std::uint64_t index) {
    if (bytes.empty()) throw Error("empty ITCH payload", offset, index);
    Message m;
    m.type = static_cast<char>(bytes[0]);
    m.offset = offset;
    m.message_index = index;
    require(payload_size(m.type) != 0, m, "unknown message type");
    require(bytes.size() == payload_size(m.type), m, "payload length mismatch");
    m.stock_locate = static_cast<std::uint16_t>(integer(bytes, 1, 2));
    m.tracking_number = static_cast<std::uint16_t>(integer(bytes, 3, 2));
    m.timestamp = integer(bytes, 5, 6);
    require(m.timestamp < day_ns, m, "timestamp outside one day");
    switch (m.type) {
    case 'S':
        m.event = static_cast<char>(bytes[11]);
        require(m.stock_locate == 0, m, "system event locate must be zero");
        require(std::string("OSQMEC").find(m.event) != std::string::npos, m, "invalid system event");
        break;
    case 'R':
        m.symbol = alpha(bytes, 11, 8);
        require(!m.symbol.empty() && printable_ascii(m.symbol), m, "invalid directory symbol");
        break;
    case 'A': case 'F':
        m.reference = integer(bytes, 11, 8);
        m.side = static_cast<char>(bytes[19]);
        m.shares = static_cast<std::uint32_t>(integer(bytes, 20, 4));
        m.symbol = alpha(bytes, 24, 8);
        m.price = static_cast<std::uint32_t>(integer(bytes, 32, 4));
        if (m.type == 'F') m.attribution = alpha(bytes, 36, 4);
        break;
    case 'E': case 'C': case 'X':
        m.reference = integer(bytes, 11, 8);
        m.shares = static_cast<std::uint32_t>(integer(bytes, 19, 4));
        if (m.type != 'X') m.match_number = integer(bytes, 23, 8);
        if (m.type == 'C') {
            m.printable = static_cast<char>(bytes[31]);
            m.price = static_cast<std::uint32_t>(integer(bytes, 32, 4));
        }
        break;
    case 'D': m.reference = integer(bytes, 11, 8); break;
    case 'U':
        m.reference = integer(bytes, 11, 8);
        m.new_reference = integer(bytes, 19, 8);
        m.shares = static_cast<std::uint32_t>(integer(bytes, 27, 4));
        m.price = static_cast<std::uint32_t>(integer(bytes, 31, 4));
        break;
    default: m.ignored = true; break;
    }
    return m;
}

void BinaryFileReader::feed(std::span<const std::uint8_t> input, const Handler& handler) {
    for (const auto byte : input) { hash_ ^= byte; hash_ *= 1099511628211ULL; }
    while (!input.empty()) {
        if (ended_) throw Error("bytes after BinaryFILE end", bytes_, messages_ + 1);
        if (expected_ == 0) {
            if (length_used_ == 0) last_offset_ = bytes_;
            while (length_used_ != 2 && !input.empty()) {
                length_[length_used_++] = input.front();
                input = input.subspan(1);
                ++bytes_;
            }
            if (length_used_ != 2) return;
            expected_ = static_cast<std::size_t>((static_cast<unsigned>(length_[0]) << 8U) | length_[1]);
            length_used_ = 0;
            if (expected_ == 0) { ended_ = true; continue; }
        }
        if (partial_.empty() && input.size() >= expected_) {
            const auto size = expected_;
            const auto message = decode(input.first(size), last_offset_, messages_ + 1);
            handler(message);
            ++messages_;
            bytes_ += size;
            input = input.subspan(size);
            expected_ = 0;
        } else {
            const auto size = std::min(expected_ - partial_.size(), input.size());
            partial_.insert(partial_.end(), input.begin(), input.begin() + static_cast<std::ptrdiff_t>(size));
            input = input.subspan(size);
            bytes_ += size;
            if (partial_.size() != expected_) return;
            handler(decode(partial_, last_offset_, messages_ + 1));
            ++messages_;
            partial_.clear();
            expected_ = 0;
        }
    }
}

void BinaryFileReader::finish() const {
    if (length_used_ != 0) throw Error("truncated length field", last_offset_, messages_ + 1);
    if (expected_ != 0) throw Error("truncated payload", last_offset_, messages_ + 1,
                                  partial_.empty() ? '?' : static_cast<char>(partial_[0]));
}

std::string BinaryFileReader::input_hash() const {
    std::ostringstream out;
    out << std::hex << std::setw(16) << std::setfill('0') << hash_;
    return out.str();
}

Reconstructor::Reconstructor(std::string symbol, std::size_t max_orders)
    : symbol_(std::move(symbol)), max_orders_(max_orders) {
    if (symbol_.empty() || symbol_.size() > 8 || !printable_ascii(symbol_) || symbol_.back() == ' ')
        throw std::invalid_argument("symbol must be 1-8 printable characters without trailing padding");
    if (max_orders == 0) throw std::invalid_argument("max-orders must be positive");
}

Reconstructor::Levels& Reconstructor::side_levels(char side) { return side == 'B' ? bids_ : asks_; }
const Reconstructor::Levels& Reconstructor::side_levels(char side) const { return side == 'B' ? bids_ : asks_; }

void Reconstructor::add(const Order& order) {
    auto& entry = side_levels(order.side).try_emplace(order.price, Level{order.side, order.price, 0, 0}).first->second;
    orders_.emplace(order.reference, order);
    entry.shares += order.shares;
    ++entry.orders;
}

void Reconstructor::remove(const Order& order) {
    auto& levels = side_levels(order.side);
    auto it = levels.find(order.price);
    assert(it != levels.end() && it->second.orders > 0 && it->second.shares >= order.shares);
    it->second.shares -= order.shares;
    if (--it->second.orders == 0) levels.erase(it);
    orders_.erase(order.reference);
}

bool Reconstructor::apply(const Message& m) {
    require(!ended_, m, "payload after ITCH End of Messages");
    require(started_ || (m.type == 'S' && m.event == 'O'), m, "first payload must be S/O");
    last_offset_ = m.offset;
    ++statistics_.messages;
    ++statistics_.counts_by_type[m.type];
    if (m.type == 'S') {
        require(m.event != 'O' || !started_, m, "duplicate session start");
        started_ = true;
        ended_ = m.event == 'C';
        statistics_.system_events += m.event;
        return false;
    }
    if (m.type == 'R') {
        if (m.symbol == symbol_) {
            require(m.stock_locate != 0, m, "target directory locate is zero");
            require(!locate_ || *locate_ == m.stock_locate, m, "target locate changed");
            const auto previous = directories_.find(m.stock_locate);
            require(previous == directories_.end() || previous->second == m.symbol,
                    m, "target locate previously assigned to another symbol");
            locate_ = m.stock_locate;
        } else {
            require(!locate_ || *locate_ != m.stock_locate, m, "target locate assigned to another symbol");
        }
        directories_.insert_or_assign(m.stock_locate, m.symbol);
    }
    if ((m.type == 'A' || m.type == 'F') && m.symbol == symbol_)
        require(locate_ && *locate_ == m.stock_locate, m, "target add has no matching directory");
    if (m.ignored) ++statistics_.ignored_by_type[m.type];
    if (!locate_ || m.stock_locate != *locate_) {
        ++statistics_.filtered_messages;
        return false;
    }
    ++statistics_.target_messages;
    if (m.ignored || m.type == 'R') return false;

    if (m.type == 'A' || m.type == 'F') {
        require(m.symbol == symbol_, m, "target locate/symbol mismatch");
        require(m.side == 'B' || m.side == 'S', m, "invalid side");
        require(m.shares > 0, m, "zero add quantity");
        require(m.price <= maximum_price, m, "price outside Price(4) range");
        require(printable_ascii(m.attribution), m, "invalid attribution");
        require(!orders_.contains(m.reference), m, "duplicate active reference");
        require(orders_.size() < max_orders_, m, "order resource limit reached");
        const auto aggregate = level(m.side, m.price).shares;
        require(aggregate <= std::numeric_limits<std::uint64_t>::max() - m.shares, m, "level quantity overflow");
        add({m.reference, m.side, m.price, m.shares, m.attribution});
    } else {
        const auto* existing = find(m.reference);
        require(existing != nullptr, m, "unknown order reference");
        const Order old = *existing;
        if (m.type == 'U') {
            require(!orders_.contains(m.new_reference), m, "replacement reference conflict");
            require(m.shares > 0, m, "zero replacement quantity");
            require(m.price <= maximum_price, m, "price outside Price(4) range");
            auto aggregate = level(old.side, m.price).shares;
            if (m.price == old.price) aggregate -= old.shares;
            require(aggregate <= std::numeric_limits<std::uint64_t>::max() - m.shares, m, "level quantity overflow");
            remove(old);
            add({m.new_reference, old.side, m.price, m.shares, old.attribution});
        } else if (m.type == 'D') {
            remove(old);
        } else {
            require(m.type == 'E' || m.type == 'C' || m.type == 'X', m, "unsupported book update");
            require(m.shares > 0 && m.shares <= old.shares, m, "invalid reduction quantity");
            if (m.type == 'C') {
                require(m.printable == 'Y' || m.printable == 'N', m, "invalid printable flag");
                require(m.price <= maximum_price, m, "execution price outside Price(4) range");
            }
            if (m.shares == old.shares) remove(old);
            else {
                orders_.at(m.reference).shares -= m.shares;
                side_levels(old.side).at(old.price).shares -= m.shares;
            }
        }
    }
    ++statistics_.updates;
    return true;
}

void Reconstructor::finish(bool binary_end, bool allow_prefix) const {
    if (!started_) throw Error("missing S/O session start", last_offset_, statistics_.messages);
    if ((!allow_prefix && (!binary_end || !ended_)) || (binary_end && !ended_))
        throw Error("incomplete session (requires S/C and BinaryFILE end)", last_offset_, statistics_.messages);
    if (!locate_) throw Error("target directory not found", last_offset_, statistics_.messages);
    if (statistics_.updates == 0) throw Error("no target book updates", last_offset_, statistics_.messages);
}

const Order* Reconstructor::find(std::uint64_t reference) const {
    const auto it = orders_.find(reference);
    return it == orders_.end() ? nullptr : &it->second;
}

Level Reconstructor::level(char side, std::uint32_t price) const {
    const auto& levels = side_levels(side);
    const auto it = levels.find(price);
    return it == levels.end() ? Level{side, price, 0, 0} : it->second;
}

Bbo Reconstructor::bbo() const {
    Bbo result;
    if (!bids_.empty()) result.bid = bids_.rbegin()->second;
    if (!asks_.empty()) result.ask = asks_.begin()->second;
    return result;
}

std::vector<Order> Reconstructor::orders() const {
    std::vector<Order> result;
    result.reserve(orders_.size());
    for (const auto& [id, order] : orders_) { (void)id; result.push_back(order); }
    std::sort(result.begin(), result.end(), [](const Order& a, const Order& b) { return a.reference < b.reference; });
    return result;
}

std::vector<Level> Reconstructor::levels() const {
    std::vector<Level> result;
    result.reserve(bids_.size() + asks_.size());
    for (auto it = bids_.rbegin(); it != bids_.rend(); ++it) result.push_back(it->second);
    for (const auto& [price, entry] : asks_) { (void)price; result.push_back(entry); }
    return result;
}

void Reconstructor::check_invariants() const {
    Levels bids, asks;
    for (const auto& [id, order] : orders_) {
        if (id != order.reference || order.shares == 0 || (order.side != 'B' && order.side != 'S'))
            throw std::logic_error("invalid order state");
        auto& entries = order.side == 'B' ? bids : asks;
        auto& entry = entries.try_emplace(order.price, Level{order.side, order.price, 0, 0}).first->second;
        if (entry.shares > std::numeric_limits<std::uint64_t>::max() - order.shares)
            throw std::logic_error("aggregate overflow");
        entry.shares += order.shares;
        ++entry.orders;
    }
    if (bids != bids_ || asks != asks_ || orders_.size() > max_orders_)
        throw std::logic_error("order/level state mismatch");
}

} // namespace llmatch::itch
