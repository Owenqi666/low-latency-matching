#include "random_commands.hpp"

#include "reference_engine.hpp"

#include <algorithm>
#include <limits>
#include <random>
#include <stdexcept>

namespace llmatch::testing {

std::vector<Command> random_commands(EngineConfig config, std::uint64_t seed, std::size_t count) {
    ReferenceEngine state(config);
    std::vector<Event> output(state.required_event_capacity());
    std::mt19937_64 random(seed);
    std::vector<Command> commands;
    commands.reserve(count);
    std::vector<Order> active;
    for (std::size_t index = 0; index < count; ++index) {
        active.clear();
        const auto snapshot = state.snapshot();
        for (const auto& level : snapshot.bids) {
            active.insert(active.end(), level.orders.begin(), level.orders.end());
        }
        for (const auto& level : snapshot.asks) {
            active.insert(active.end(), level.orders.begin(), level.orders.end());
        }
        const auto request = static_cast<RequestId>(index) + 1;
        const OrderId fresh_id = request;
        const ClientId client = static_cast<ClientId>(random() % 5 + 1);
        const Side side = random() % 2 == 0 ? Side::Buy : Side::Sell;
        // Most prices crowd three adjacent ticks; a minority explore sparse levels.
        const Price price = random() % 4 == 0
            ? static_cast<Price>(1 + random() % static_cast<std::uint64_t>(config.max_price))
            : std::min(config.max_price, static_cast<Price>(99 + random() % 3));
        const Quantity qty = 1 + random() % std::min<Quantity>(config.max_order_qty, 16);
        const auto operation = random() % 100;
        Command command{client, request, LimitOrder{fresh_id, side, price, qty}};
        if (operation < 40) {
            // Keep the default limit, including full-book admission boundaries.
        } else if (operation < 60) {
            const Quantity sweep_qty = random() % 3 == 0 ? config.max_order_qty : qty;
            command.payload = MarketOrder{fresh_id, side, sweep_qty};
        } else if (operation < 82) {
            if (!active.empty() && random() % 5 != 0) {
                const auto& chosen = active[static_cast<std::size_t>(random() % active.size())];
                command.client = chosen.owner;
                command.payload = CancelOrder{chosen.id};
            } else {
                command.payload = CancelOrder{fresh_id};
            }
        } else if (operation < 90 && !active.empty()) {
            const auto& chosen = active[static_cast<std::size_t>(random() % active.size())];
            if (random() % 2 == 0) {
                command.payload = LimitOrder{chosen.id, side, price, qty};
            } else {
                command.client = static_cast<ClientId>(chosen.owner % 5 + 1);
                command.payload = CancelOrder{chosen.id};
            }
        } else {
            auto& limit = std::get<LimitOrder>(command.payload);
            switch (random() % 9) {
                case 0: command.client = 0; break;
                case 1: command.request = 0; break;
                case 2: limit.id = 0; break;
                case 3: limit.side = static_cast<Side>(2); break;
                case 4: limit.qty = 0; break;
                case 5:
                    limit.qty = config.max_order_qty == std::numeric_limits<Quantity>::max()
                        ? 0 : config.max_order_qty + 1;
                    break;
                case 6: limit.price = 0; break;
                case 7: limit.price = -1; break;
                case 8: // Several invalid fields exercise deterministic precedence.
                    command.client = 0;
                    limit.side = static_cast<Side>(255);
                    limit.qty = 0;
                    limit.price = -1;
                    break;
            }
        }
        commands.push_back(command);
        const auto result = state.process(command, output);
        if (result.status != ProcessStatus::Processed) {
            throw std::runtime_error("generator oracle could not process its command");
        }
    }
    return commands;
}

}
