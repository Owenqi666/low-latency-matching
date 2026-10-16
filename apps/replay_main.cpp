#include "differential.hpp"
#include "llmatch/matching_engine.hpp"
#include "reference_engine.hpp"
#include "trace_io.hpp"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
template <class Engine>
void replay(llmatch::EngineConfig config, const std::vector<llmatch::Command>& commands,
            const std::filesystem::path& directory) {
    Engine engine(config);
    std::vector<llmatch::Event> output(engine.required_event_capacity());
    std::ofstream events(directory / "events.txt");
    events.exceptions(std::ios::failbit | std::ios::badbit);
    events << "LLMATCH_EVENTS 1\n";
    for (std::size_t index = 0; index < commands.size(); ++index) {
        const auto result = engine.process(commands[index], output);
        if (result.status != llmatch::ProcessStatus::Processed) {
            throw std::runtime_error("call-level error at command " + std::to_string(index + 1));
        }
        engine.check_invariants();
        llmatch::trace::write_events(events, std::span(output).first(result.event_count));
    }
    events.close();
    std::ofstream snapshot(directory / "snapshot.txt");
    snapshot.exceptions(std::ios::failbit | std::ios::badbit);
    llmatch::trace::write_snapshot(snapshot, engine.snapshot());
    snapshot.close();
}
}

int main(int argc, char** argv) {
    try {
        std::string engine;
        std::filesystem::path config_path, input_path, output_directory;
        for (int index = 1; index < argc; ++index) {
            const std::string option = argv[index];
            if (index + 1 == argc) throw std::invalid_argument("missing value for " + option);
            const std::string value = argv[++index];
            if (option == "--engine") engine = value;
            else if (option == "--config") config_path = value;
            else if (option == "--input") input_path = value;
            else if (option == "--output-dir") output_directory = value;
            else throw std::invalid_argument("unknown option " + option);
        }
        if ((engine != "baseline" && engine != "reference" && engine != "compare") ||
            config_path.empty() || input_path.empty() || output_directory.empty()) {
            throw std::invalid_argument("usage: replay --engine baseline|reference|compare --config FILE --input FILE --output-dir DIR");
        }
        const auto config = llmatch::trace::read_config(config_path);
        const auto commands = llmatch::trace::read_trace(input_path);
        if (engine == "compare") {
            if (const auto difference = llmatch::validation::compare(config, commands)) {
                llmatch::validation::save_failure(output_directory, config, commands, *difference);
                const std::filesystem::path source_metadata = input_path.string() + ".meta";
                if (std::filesystem::exists(source_metadata)) {
                    std::filesystem::copy_file(source_metadata, output_directory / "source.metadata.txt",
                                               std::filesystem::copy_options::overwrite_existing);
                }
                std::cerr << "difference at command " << difference->command_index + 1 << ": "
                          << llmatch::validation::difference_name(*difference) << '\n';
                return 2;
            }
        }
        std::filesystem::create_directories(output_directory);
        if (engine == "reference") replay<llmatch::ReferenceEngine>(config, commands, output_directory);
        else replay<llmatch::MatchingEngine>(config, commands, output_directory);
        std::ofstream report(output_directory / "report.txt");
        report.exceptions(std::ios::failbit | std::ios::badbit);
        report << "engine " << engine << "\ncommands " << commands.size()
               << "\ninput_hash " << llmatch::trace::file_hash(input_path)
               << "\nconfig_hash " << llmatch::trace::file_hash(config_path)
               << "\nresult passed\n";
        report.close();
        std::cout << "replayed " << commands.size() << " commands (" << engine << ")\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "replay: " << error.what() << '\n';
        return 1;
    }
}
