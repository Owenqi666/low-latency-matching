#pragma once

#include "llmatch/command.hpp"
#include <vector>

namespace llmatch::testing {
inline constexpr const char* generator_version = "mt19937_64-modulo-v1";
std::vector<Command> random_commands(EngineConfig config, std::uint64_t seed, std::size_t count);
}
