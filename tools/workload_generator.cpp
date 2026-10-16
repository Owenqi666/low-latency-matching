#include "random_commands.hpp"
#include "reference_engine.hpp"
#include "trace_io.hpp"

#include <charconv>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
template <class Integer>
Integer number(const std::string& text, const std::string& option) {
    Integer value{};
    const auto result = std::from_chars(text.data(), text.data() + text.size(), value);
    if (result.ec != std::errc{} || result.ptr != text.data() + text.size()) {
        throw std::invalid_argument("invalid integer for " + option + ": " + text);
    }
    return value;
}
}

int main(int argc, char** argv) {
    try {
        std::filesystem::path config_path, output_path;
        std::uint64_t seed = 0;
        std::size_t count = 0;
        bool has_seed = false;
        bool has_count = false;
        for (int index = 1; index < argc; ++index) {
            const std::string option = argv[index];
            if (index + 1 == argc) throw std::invalid_argument("missing value for " + option);
            const std::string value = argv[++index];
            if (option == "--config") config_path = value;
            else if (option == "--output") output_path = value;
            else if (option == "--seed") { seed = number<std::uint64_t>(value, option); has_seed = true; }
            else if (option == "--count") { count = number<std::size_t>(value, option); has_count = true; }
            else throw std::invalid_argument("unknown option " + option);
        }
        if (config_path.empty() || output_path.empty() || !has_seed || !has_count) {
            throw std::invalid_argument("usage: generate_workload --config FILE --seed UINT64 --count SIZE --output FILE");
        }
        const auto config = llmatch::trace::read_config(config_path);
        const auto commands = llmatch::testing::random_commands(config, seed, count);
        if (!output_path.parent_path().empty()) std::filesystem::create_directories(output_path.parent_path());
        llmatch::trace::write_trace(output_path, commands);
        std::size_t limits = 0, markets = 0, cancels = 0, accepted = 0, rejected = 0, trades = 0;
        llmatch::ReferenceEngine oracle(config);
        std::vector<llmatch::Event> output(oracle.required_event_capacity());
        for (const auto& command : commands) {
            switch (llmatch::command_kind(command)) {
                case llmatch::CommandKind::Limit: ++limits; break;
                case llmatch::CommandKind::Market: ++markets; break;
                case llmatch::CommandKind::Cancel: ++cancels; break;
            }
            const auto result = oracle.process(command, output);
            for (const auto& event : std::span(output).first(result.event_count)) {
                accepted += event.kind == llmatch::EventKind::Accepted;
                rejected += event.kind == llmatch::EventKind::Rejected;
                trades += event.kind == llmatch::EventKind::Trade;
            }
        }
        std::ofstream metadata(output_path.string() + ".meta");
        metadata.exceptions(std::ios::failbit | std::ios::badbit);
        metadata << "generator_version " << llmatch::testing::generator_version
                 << "\nseed " << seed << "\ncommands " << commands.size()
                 << "\ncapacity " << config.max_live_orders << "\nmax_price " << config.max_price
                 << "\nmax_order_qty " << config.max_order_qty
                 << "\nlimits " << limits << "\nmarkets " << markets << "\ncancels " << cancels
                 << "\naccepted " << accepted << "\nrejected " << rejected << "\ntrades " << trades
                 << "\ninput_hash " << llmatch::trace::file_hash(output_path)
                 << "\nconfig_hash " << llmatch::trace::file_hash(config_path)
                 << "\npurpose correctness; includes explicitly invalid business commands\n";
        metadata.close();
        std::cout << "generated " << commands.size() << " commands, seed " << seed << ", "
                  << llmatch::trace::file_hash(output_path) << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "generate_workload: " << error.what() << '\n';
        return 1;
    }
}
