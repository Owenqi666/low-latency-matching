# ADR 007: Reconstruct visible ITCH orders independently

Status: accepted for M5 implementation.

ITCH publishes changes to orders identified by exchange references. These
events are not original client requests and cannot be passed to MatchingEngine
to reproduce the exchange's hidden liquidity or priority decisions.

M5 therefore uses an independent offline decoder and single-symbol reconstructor:
an order-reference hash table plus ordered price aggregates. It applies the
published changes directly, retaining the existing matching service unchanged.
An independent Python decoder and dictionary model check the original bytes.

This keeps the supported contract small and testable. It deliberately does not
introduce a common engine interface, event bus, allocator framework, live feed
backend or runtime storage selection. Input/state checks occur at their owning
boundary; full invariant scans are explicit verification work.
