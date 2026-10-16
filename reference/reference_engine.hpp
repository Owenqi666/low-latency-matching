#pragma once

#include "llmatch/event.hpp"
#include "llmatch/snapshot.hpp"
#include <span>

namespace llmatch {

// Deliberately independent oracle: no production book or matching helpers.
class ReferenceEngine {
public:
    explicit ReferenceEngine(EngineConfig config);
    ReferenceEngine(const ReferenceEngine&) = delete;
    ReferenceEngine& operator=(const ReferenceEngine&) = delete;
    ReferenceEngine(ReferenceEngine&&) = delete;
    ReferenceEngine& operator=(ReferenceEngine&&) = delete;

    std::size_t required_event_capacity() const;
    ProcessResult process(const Command&, std::span<Event> output);
    BookSnapshot snapshot() const;
    void check_invariants() const;

private:
    friend struct EngineTestAccess;
    EngineConfig config_;
    std::vector<Order> orders_;
    Sequence command_seq_{};
    Sequence event_seq_{};
};

} // namespace llmatch
