#include "differential.hpp"
#include "trace_io.hpp"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    try {
        std::filesystem::path config_path, input_path, output_path, report_path;
        for (int index = 1; index < argc; ++index) {
            const std::string option = argv[index];
            if (index + 1 == argc) throw std::invalid_argument("missing value for " + option);
            const std::string value = argv[++index];
            if (option == "--config") config_path = value;
            else if (option == "--input") input_path = value;
            else if (option == "--output") output_path = value;
            else if (option == "--report") report_path = value;
            else throw std::invalid_argument("unknown option " + option);
        }
        if (config_path.empty() || input_path.empty() || output_path.empty()) {
            throw std::invalid_argument("usage: shrink_failure --config FILE --input FILE --output FILE [--report FILE]");
        }
        const auto config = llmatch::trace::read_config(config_path);
        auto current = llmatch::trace::read_trace(input_path);
        const auto initial = llmatch::validation::compare(config, current);
        if (!initial) throw std::runtime_error("input has no differential failure to shrink");
        const std::size_t original_size = current.size();
        std::size_t trials = 1;
        std::size_t partitions = 2;
        while (current.size() >= 2) {
            const std::size_t chunk = current.size() / partitions + (current.size() % partitions != 0);
            bool reduced = false;
            for (std::size_t start = 0; start < current.size(); start += chunk) {
                const std::size_t end = start + std::min(chunk, current.size() - start);
                std::vector<llmatch::Command> candidate;
                candidate.reserve(current.size() - (end - start));
                candidate.insert(candidate.end(), current.begin(), current.begin() + static_cast<std::ptrdiff_t>(start));
                candidate.insert(candidate.end(), current.begin() + static_cast<std::ptrdiff_t>(end), current.end());
                ++trials;
                const auto difference = llmatch::validation::compare(config, candidate);
                if (difference && llmatch::validation::same_failure_kind(*initial, *difference)) {
                    current = std::move(candidate);
                    partitions = std::max<std::size_t>(2, partitions - 1);
                    reduced = true;
                    break;
                }
            }
            if (!reduced) {
                if (partitions >= current.size()) break;
                partitions = std::min(current.size(), partitions * 2);
            }
        }
        const auto final = llmatch::validation::compare(config, current);
        if (!final || !llmatch::validation::same_failure_kind(*initial, *final)) {
            throw std::logic_error("minimized input lost its failure class");
        }
        if (!output_path.parent_path().empty()) std::filesystem::create_directories(output_path.parent_path());
        llmatch::trace::write_trace(output_path, current);
        if (report_path.empty()) report_path = output_path.string() + ".report.txt";
        std::ofstream report(report_path);
        report.exceptions(std::ios::failbit | std::ios::badbit);
        report << "original_commands " << original_size << "\nminimized_commands " << current.size()
               << "\ncandidate_replays " << trials
               << "\ninput_hash " << llmatch::trace::file_hash(input_path)
               << "\nminimized_hash " << llmatch::trace::file_hash(output_path) << '\n';
        llmatch::validation::write_difference(report, *final);
        report.close();
        std::cout << "shrunk " << original_size << " to " << current.size() << " commands in " << trials
                  << " candidate replays (" << llmatch::validation::difference_name(*final) << ")\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "shrink_failure: " << error.what() << '\n';
        return 1;
    }
}
