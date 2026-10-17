#pragma once

#include "llmatch/event.hpp"
#include "llmatch/order_book.hpp"

#include <span>

namespace llmatch {

enum class CallError : std::uint8_t { None, Busy, SequenceExhausted };

class MatchingEngine {
public:
    explicit MatchingEngine(EngineConfig config);
    MatchingEngine(const MatchingEngine&) = delete;
    MatchingEngine& operator=(const MatchingEngine&) = delete;
    MatchingEngine(MatchingEngine&&) = delete;
    MatchingEngine& operator=(MatchingEngine&&) = delete;

    std::size_t required_event_capacity() const noexcept;
    // One owner thread. begin does not mutate the book; call errors change nothing.
    CallError begin(const Command& command);
    bool active() const noexcept;
    // Caller reserves an output slot before advancing. Idle leaves output untouched.
    // Complete makes the engine idle; transport must publish it before another begin.
    bool next(Event& output);
    // Synchronous use requires an idle engine and retains the M1 C+4 contract.
    ProcessResult process(const Command& command, std::span<Event> output);
    TopOfBook top_of_book() const noexcept;
    BookSnapshot snapshot() const;
    void check_invariants() const;

private:
    friend struct EngineTestAccess;
    friend struct PausableEngineTestAccess;
    enum class Phase : std::uint8_t { Idle, Admission, Execution, Complete };
    RejectReason validate(const Command& command) const;
    Event make_event(EventKind kind);

    EngineConfig config_;
    std::size_t event_capacity_;
    OrderBook book_;
    Sequence command_seq_{};
    Sequence event_seq_{};
    Command current_{};
    Phase phase_{Phase::Idle};
    RejectReason rejection_{};
    Quantity remaining_{};
    Quantity filled_{};
    Quantity resting_{};
    Quantity cancelled_{};
};

}
