#pragma once

#include "llmatch/event.hpp"
#include "llmatch/snapshot.hpp"
#include <filesystem>
#include <iosfwd>
#include <span>
#include <string>
#include <vector>

namespace llmatch::trace {

EngineConfig read_config(const std::filesystem::path& path);
void write_config(const std::filesystem::path& path, const EngineConfig& config);
std::vector<Command> read_trace(const std::filesystem::path& path);
void write_trace(const std::filesystem::path& path, std::span<const Command> commands);
void write_events(std::ostream& output, std::span<const Event> events);
void write_snapshot(std::ostream& output, const BookSnapshot& snapshot);
std::string file_hash(const std::filesystem::path& path);

} // namespace llmatch::trace
