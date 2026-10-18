#include "deep_book_commands.hpp"

#include "reference_engine.hpp"
#include "trace_io.hpp"

#include <algorithm>
#include <fstream>
#include <limits>
#include <optional>
#include <random>
#include <set>
#include <stdexcept>
#include <utility>

namespace llmatch::testing {
namespace {
using LevelKey = std::pair<Side, Price>;

const LevelSnapshot* find_level(const BookSnapshot& book, Side side, Price price) {
    const auto& levels = side == Side::Buy ? book.bids : book.asks;
    const auto found = std::lower_bound(levels.begin(), levels.end(), price,
        [side](const LevelSnapshot& level, Price value) {
            return side == Side::Buy ? level.price > value : level.price < value;
        });
    return found != levels.end() && found->price == price ? &*found : nullptr;
}

const Order* find_order(const BookSnapshot& book, OrderId id) {
    for (const auto* levels : {&book.bids, &book.asks}) {
        for (const auto& level : *levels) {
            for (const auto& order : level.orders) if (order.id == id) return &order;
        }
    }
    return nullptr;
}

DeepBookSample sample(const BookSnapshot& book, std::size_t number, DeepBookPhase phase) {
    DeepBookSample result{number, phase, 0, book.bids.size() + book.asks.size(), 0, 0, 0};
    for (const auto* levels : {&book.bids, &book.asks}) {
        for (const auto& level : *levels) {
            result.live_orders += level.orders.size();
            result.max_fifo_depth = std::max(result.max_fifo_depth, level.orders.size());
            if (result.minimum_price == 0 || level.price < result.minimum_price) result.minimum_price = level.price;
            result.maximum_price = std::max(result.maximum_price, level.price);
        }
    }
    return result;
}

class Generator {
public:
    Generator(EngineConfig config, std::uint64_t seed, DeepBookDistribution distribution)
        : config_(config), distribution_(distribution), oracle_(config), random_(seed),
          output_(oracle_.required_event_capacity()) {
        if (config.max_live_orders < 32 || config.max_order_qty < 32 ||
            config.max_live_orders > static_cast<std::size_t>(std::numeric_limits<Price>::max() / 64) ||
            config.max_price < static_cast<Price>(config.max_live_orders) * 64) {
            throw std::invalid_argument("deep-book generator requires C>=32, max_order_qty>=32 and max_price>=64*C");
        }
        if (distribution != DeepBookDistribution::LongFifo && distribution != DeepBookDistribution::SparseWide) {
            throw std::invalid_argument("unknown deep-book distribution");
        }
    }

    DeepBookTrace run(std::size_t tail_commands) {
        if (tail_commands < 32) throw std::invalid_argument("deep-book tail requires at least 32 commands");
        const auto target = config_.max_live_orders * 85 / 100;
        while (live_orders() < target) add_resting(DeepBookPhase::Prefill);
        const auto tail_start = result_.commands.size();
        exercise_tail_paths();
        while (result_.commands.size() - tail_start < tail_commands) {
            const auto remaining = tail_commands - (result_.commands.size() - tail_start);
            if (live_orders() < target) {
                add_resting(DeepBookPhase::Tail);
                continue;
            }
            const auto operation = random_() % 100;
            if (operation < 35 && live_orders() < config_.max_live_orders * 90 / 100) {
                add_resting(DeepBookPhase::Tail);
            } else if (operation < 60) {
                cancel(choose_order(), DeepBookPhase::Tail);
            } else if (operation < 70) {
                partial_fill();
            } else if (operation < 80) {
                wrong_owner();
            } else if (operation < 90) {
                duplicate();
            } else if (remaining >= 2) {
                const auto order = choose_order();
                cancel(order, DeepBookPhase::Tail);
                add_at(order.side, order.price, 8, DeepBookPhase::Tail, order.id);
            } else {
                wrong_owner();
            }
        }
        // Reaching full capacity necessarily adds O(C) commands; do not hide them
        // in the fixed-size random tail or claim they satisfy ordinary occupancy.
        while (live_orders() < config_.max_live_orders) add_resting(DeepBookPhase::CapacityBoundary);
        add_resting(DeepBookPhase::CapacityBoundary); // Observed CapacityExceeded.
        while (live_orders() > target) cancel(choose_order(), DeepBookPhase::CapacityBoundary);
        return std::move(result_);
    }

private:
    std::size_t live_orders() const { return result_.samples.empty() ? 0 : result_.samples.back().live_orders; }
    OrderId fresh_id() { return next_id_++; }
    ClientId client() { return static_cast<ClientId>(1 + random_() % 7); }

    Order choose_order() {
        const auto& preferred = random_() % 2 == 0 ? book_.bids : book_.asks;
        const auto& levels = preferred.empty() ? (book_.bids.empty() ? book_.asks : book_.bids) : preferred;
        if (levels.empty()) throw std::logic_error("deep-book selection from empty book");
        const auto& level = levels[static_cast<std::size_t>(random_() % levels.size())];
        return level.orders[static_cast<std::size_t>(random_() % level.orders.size())];
    }

    Price resting_price(Side side) {
        const Price anchor = side == Side::Buy ? config_.max_price / 4 : config_.max_price / 4 * 3;
        if (distribution_ == DeepBookDistribution::LongFifo) {
            const auto offset = static_cast<Price>(random_() % 3);
            return side == Side::Buy ? anchor - offset : anchor + offset;
        }
        const auto slots = config_.max_live_orders * 2;
        const auto step = config_.max_price / static_cast<Price>(config_.max_live_orders * 16);
        auto& cursor = side == Side::Buy ? next_bid_price_ : next_ask_price_;
        for (std::size_t tries = 0; tries < slots; ++tries) {
            const auto offset = static_cast<Price>(cursor++ % slots) * step;
            const Price price = side == Side::Buy ? anchor - offset : anchor + offset;
            if (find_level(book_, side, price) == nullptr) return price;
        }
        throw std::logic_error("deep-book sparse price range exhausted");
    }

    void add_at(Side side, Price price, Quantity quantity, DeepBookPhase phase,
                std::optional<OrderId> reused_id = std::nullopt) {
        const auto id = reused_id ? *reused_id : fresh_id();
        emit({client(), 0, LimitOrder{id, side, price, quantity}}, phase);
    }

    void add_resting(DeepBookPhase phase) {
        const Side side = random_() % 2 == 0 ? Side::Buy : Side::Sell;
        const auto price = resting_price(side);
        const Quantity quantity = 8 + random_() % 9;
        add_at(side, price, quantity, phase);
    }

    void cancel(const Order& order, DeepBookPhase phase) {
        emit({order.owner, 0, CancelOrder{order.id}}, phase);
    }

    void partial_fill() {
        const bool buy = book_.bids.empty() || (!book_.asks.empty() && random_() % 2 == 0);
        emit({client(), 0, MarketOrder{fresh_id(), buy ? Side::Buy : Side::Sell, 1}}, DeepBookPhase::Tail);
    }

    void wrong_owner() {
        const auto order = choose_order();
        emit({static_cast<ClientId>(order.owner % 7 + 1), 0, CancelOrder{order.id}}, DeepBookPhase::Tail);
    }

    void duplicate() {
        const auto order = choose_order();
        emit({order.owner, 0, LimitOrder{order.id, order.side, order.price, 8}}, DeepBookPhase::Tail);
    }

    void exercise_tail_paths() {
        // Sparse books still explicitly exercise linked FIFO head/middle/tail
        // deletion at one level, without losing their overall sparse distribution.
        const auto chosen = choose_order();
        while (find_level(book_, chosen.side, chosen.price)->orders.size() < 4) {
            add_at(chosen.side, chosen.price, 8, DeepBookPhase::Tail);
        }
        cancel(find_level(book_, chosen.side, chosen.price)->orders.front(), DeepBookPhase::Tail);
        auto* level = find_level(book_, chosen.side, chosen.price);
        cancel(level->orders[level->orders.size() / 2], DeepBookPhase::Tail);
        cancel(find_level(book_, chosen.side, chosen.price)->orders.back(), DeepBookPhase::Tail);
        partial_fill();

        // Two tiny, noncrossing levels inside the spread make a genuine multi-
        // price sweep possible without destroying a deep FIFO's occupancy.
        const Price near = config_.max_price / 2;
        add_at(Side::Sell, near + 10, 2, DeepBookPhase::Tail);
        const auto second_id = next_id_;
        add_at(Side::Sell, near + 20, 2, DeepBookPhase::Tail);
        emit({client(), 0, MarketOrder{fresh_id(), Side::Buy, 3}}, DeepBookPhase::Tail);
        const auto remaining = *find_order(book_, second_id);
        cancel(remaining, DeepBookPhase::Tail);

        const auto reusable_id = next_id_;
        add_at(Side::Sell, near + 30, 8, DeepBookPhase::Tail);
        const auto reusable = *find_order(book_, reusable_id);
        cancel(reusable, DeepBookPhase::Tail);
        add_at(Side::Sell, near + 30, 8, DeepBookPhase::Tail, reusable_id);
        wrong_owner();
        duplicate();
    }

    void emit(Command command, DeepBookPhase phase) {
        command.request = static_cast<RequestId>(result_.commands.size()) + 1;
        const auto processed = oracle_.process(command, output_);
        if (processed.status != ProcessStatus::Processed) throw std::runtime_error("deep-book oracle call failed");
        const auto events = std::span(output_).first(processed.event_count);
        auto after = oracle_.snapshot();
        std::set<LevelKey> affected_levels;
        std::set<Price> traded_prices;
        bool accepted = false, rested = false;
        auto& counts = result_.operations;
        const auto count = [&](const std::string& name) {
            ++counts[name];
            ++counts[std::string(deep_book_phase_name(phase)) + "." + name];
        };
        count(command_kind(command) == CommandKind::Limit ? "limit_commands" :
              command_kind(command) == CommandKind::Market ? "market_commands" : "cancel_commands");
        for (const auto& event : events) {
            switch (event.kind) {
                case EventKind::Accepted:
                    accepted = true;
                    count("accepted_commands");
                    break;
                case EventKind::Rejected:
                    count("rejected_commands");
                    if (event.reject_reason == RejectReason::NotOwner) count("wrong_owner_rejections");
                    if (event.reject_reason == RejectReason::DuplicateOrder) count("duplicate_active_id_rejections");
                    if (event.reject_reason == RejectReason::CapacityExceeded) count("full_capacity_rejections");
                    break;
                case EventKind::Cancelled:
                    if (event.cancel_reason == CancelReason::UserCancel) {
                        const auto* order = find_order(book_, event.order_id);
                        if (!order) throw std::logic_error("cancel event has no prior maker");
                        const auto* level = find_level(book_, order->side, order->price);
                        const auto found = std::find_if(level->orders.begin(), level->orders.end(),
                            [order](const Order& value) { return value.id == order->id; });
                        const auto position = static_cast<std::size_t>(found - level->orders.begin());
                        if (level->orders.size() == 1) count("cancel_singleton");
                        else {
                            if (position == 0) count("cancel_head");
                            else if (position + 1 == level->orders.size()) count("cancel_tail");
                            else count("cancel_middle");
                        }
                        affected_levels.emplace(order->side, order->price);
                        terminated_ids_.insert(order->id);
                    }
                    break;
                case EventKind::Trade: {
                    const auto* maker = find_order(book_, event.maker_id);
                    if (!maker) throw std::logic_error("trade event has no prior maker");
                    count("trade_events");
                    if (event.qty < maker->remaining) count("partial_maker_fills");
                    else terminated_ids_.insert(maker->id);
                    affected_levels.emplace(maker->side, maker->price);
                    traded_prices.insert(event.price);
                    break;
                }
                case EventKind::Rested:
                    rested = true;
                    if (deleted_levels_.contains({event.side, event.price}) &&
                        find_level(book_, event.side, event.price) == nullptr) count("level_rebuilds");
                    break;
                case EventKind::CommandComplete: break;
            }
        }
        if (traded_prices.size() >= 2) count("multi_price_sweep_commands");
        if (accepted && command_kind(command) != CommandKind::Cancel) {
            if (terminated_ids_.contains(order_id(command))) count("terminal_id_reuses");
            if (!rested) terminated_ids_.insert(order_id(command));
        }
        for (const auto& key : affected_levels) {
            if (find_level(after, key.first, key.second) == nullptr) {
                deleted_levels_.insert(key);
                count("levels_deleted");
            }
        }
        result_.commands.push_back(command);
        result_.samples.push_back(sample(after, result_.commands.size(), phase));
        book_ = std::move(after);
    }

    EngineConfig config_;
    DeepBookDistribution distribution_;
    ReferenceEngine oracle_;
    std::mt19937_64 random_;
    std::vector<Event> output_;
    BookSnapshot book_;
    DeepBookTrace result_;
    OrderId next_id_{1};
    std::size_t next_bid_price_{}, next_ask_price_{};
    std::set<OrderId> terminated_ids_;
    std::set<LevelKey> deleted_levels_;
};
} // namespace

const char* deep_book_distribution_name(DeepBookDistribution distribution) {
    switch (distribution) {
        case DeepBookDistribution::LongFifo: return "long_fifo";
        case DeepBookDistribution::SparseWide: return "sparse_wide";
    }
    throw std::invalid_argument("unknown deep-book distribution");
}

const char* deep_book_phase_name(DeepBookPhase phase) {
    switch (phase) {
        case DeepBookPhase::Prefill: return "prefill";
        case DeepBookPhase::Tail: return "tail";
        case DeepBookPhase::CapacityBoundary: return "capacity_boundary";
    }
    throw std::invalid_argument("unknown deep-book phase");
}

DeepBookTrace deep_book_commands(EngineConfig config, std::uint64_t seed,
                                 DeepBookDistribution distribution, std::size_t tail_commands) {
    return Generator(config, seed, distribution).run(tail_commands);
}

void save_deep_book(const std::filesystem::path& directory, EngineConfig config,
                   std::uint64_t seed, DeepBookDistribution distribution,
                   const DeepBookTrace& generated) {
    if (generated.commands.size() != generated.samples.size()) throw std::invalid_argument("incomplete deep-book samples");
    std::filesystem::create_directories(directory);
    trace::write_config(directory / "config.txt", config);
    trace::write_trace(directory / "input.trace", generated.commands);
    std::ofstream coverage(directory / "coverage.csv");
    coverage.exceptions(std::ios::failbit | std::ios::badbit);
    coverage << "command_number,phase,live_orders,price_levels,max_fifo_depth,minimum_price,maximum_price,price_span\n";
    std::size_t prefill = 0, tail = 0, boundary = 0, tail_in_band = 0, sparse_in_band = 0;
    for (const auto& value : generated.samples) {
        coverage << value.command_number << ',' << deep_book_phase_name(value.phase) << ',' << value.live_orders
                 << ',' << value.price_levels << ',' << value.max_fifo_depth << ',' << value.minimum_price
                 << ',' << value.maximum_price << ',' << value.maximum_price - value.minimum_price << '\n';
        if (value.phase == DeepBookPhase::Prefill) ++prefill;
        else if (value.phase == DeepBookPhase::CapacityBoundary) ++boundary;
        else {
            ++tail;
            if (value.live_orders >= config.max_live_orders * 80 / 100 &&
                value.live_orders <= config.max_live_orders * 95 / 100) {
                ++tail_in_band;
                if (value.price_levels >= config.max_live_orders / 2) ++sparse_in_band;
            }
        }
    }
    coverage.close();
    std::ofstream metadata(directory / "metadata.txt");
    metadata.exceptions(std::ios::failbit | std::ios::badbit);
    metadata << "generator_version " << deep_book_generator_version
             << "\nseed " << seed << "\ndistribution " << deep_book_distribution_name(distribution)
             << "\ncapacity " << config.max_live_orders << "\nmax_price " << config.max_price
             << "\nmax_order_qty " << config.max_order_qty << "\ncommands " << generated.commands.size()
             << "\nprefill_commands " << prefill << "\ntail_commands " << tail
             << "\ncapacity_boundary_commands " << boundary << "\ntail_in_80_to_95_percent_band " << tail_in_band
             << "\ntail_in_band_with_at_least_half_capacity_levels " << sparse_in_band
             << "\ninput_hash " << trace::file_hash(directory / "input.trace")
             << "\nconfig_hash " << trace::file_hash(directory / "config.txt")
             << "\ncoverage_hash " << trace::file_hash(directory / "coverage.csv")
             << "\ncoverage_source reference events and complete before/after snapshots"
             << "\nboundary_policy capacity_boundary is excluded from ordinary tail occupancy; all commands are saved and compared\n";
    for (const auto& [name, count] : generated.operations) metadata << name << ' ' << count << '\n';
    metadata.close();
    // Existing replay attaches this sidecar to failures for external traces.
    std::filesystem::copy_file(directory / "metadata.txt", directory / "input.trace.meta",
                               std::filesystem::copy_options::overwrite_existing);
}

} // namespace llmatch::testing
