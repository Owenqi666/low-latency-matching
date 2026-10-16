#pragma once

#include "llmatch/event.hpp"
#include "llmatch/order_book.hpp"

#include <span>

namespace llmatch {

class MatchingEngine {
public:
    explicit MatchingEngine(EngineConfig config);
    MatchingEngine(const MatchingEngine&) = delete;
    MatchingEngine& operator=(const MatchingEngine&) = delete;
    MatchingEngine(MatchingEngine&&) = delete;
    MatchingEngine& operator=(MatchingEngine&&) = delete;

    std::size_t required_event_capacity() const noexcept;
    ProcessResult process(const Command& command, std::span<Event> output);
    BookSnapshot snapshot() const;
    void check_invariants() const;

private:
    friend struct EngineTestAccess;
    RejectReason validate(const Command& command) const;

    EngineConfig config_;
    std::size_t event_capacity_;
    OrderBook book_;
    Sequence command_seq_{};
    Sequence event_seq_{};
};

}
