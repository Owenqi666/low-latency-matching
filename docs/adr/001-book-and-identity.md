# ADR 001: price levels, FIFO storage and active identity

Status: implemented in the M1 baseline.

## Context

The first version must express price/FIFO priority clearly, support cancellation
by order ID and expose enough state to verify every command. It also needs an
independent correctness oracle. Optimizing an unmeasured representation would
obscure these requirements.

## Decision

The production book uses ascending `std::map` price levels on each side,
`std::list<Order>` FIFO nodes and an `unordered_map<OrderId, Locator>` index.
Bid access uses the highest map entry; ask access uses the lowest. A locator
holds side, price-level iterator and list iterator. Mutations are centralized in
insert, fill and erase operations. The index is removed before its node and an
empty level is removed last. Engines cannot be copied or moved because their
locators refer into owned containers.

The reference uses a vector, linear searches and explicit price/arrival sequence
comparison. Swap deletion intentionally changes its physical order: FIFO must
survive this. It shares value contracts, never production business logic.

Client identity is ownership metadata only. Active OrderIds are globally unique;
terminal IDs can be reused. RequestIds correlate outputs but are not deduplicated.
An old cancel can therefore target a reused ID owned by the same client. This is
documented, deterministic M1 behavior, not a session recovery protocol.

## Consequences and alternatives

The baseline allocates map/list nodes and follows pointers. Reserving the hash
table does not eliminate these allocations. Hash lookup is average constant
time, not a worst-case guarantee; complete cancel also maintains price levels.
This version does not promise worst-case constant-time cancellation.

A flat vector for production would simplify storage but make lookup and maker
selection scans frequent. Intrusive/preallocated storage could change allocation
and locality costs, but needs a measured baseline and independent validation
first. Neither alternative is required to complete M1.

The tests exercise FIFO after partial fills and middle deletion, index rehash,
head/tail/last-node removal, ID reuse and owner rejection. Reconsider storage only
after profiling identifies a cost worth isolating in a same-input experiment.
