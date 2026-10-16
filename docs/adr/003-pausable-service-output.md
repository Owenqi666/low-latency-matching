# ADR 003: pause matching at bounded output boundaries

Status: implemented; service integration acceptance in progress.

M1's synchronous `C+4` output span is useful for replay and core measurement, but
is not network backpressure. A sweep may produce more results than the service
queue can hold. We preserve one current command and advance it one event at a
time into reserved storage. A fixed two-message pending array holds the final
BBO and Complete when both are needed. A one-slot event queue can publish them
over separate iterations. Later commands wait until Complete publication.

The synchronous adapter drains the same state machine; the vector reference
remains independent. This avoids two production matching implementations. BBO is
derived only from the final command state and does not renumber M1 business events.

A condition variable provides phase-specific waiting. Gateway admission never
blocks its event consumption or socket handling. Coalesced notifications and
bounded callback budgets prevent a hidden unbounded task queue. This baseline
accepts wake-up/mutex overhead without claiming an optimal waiting strategy.

Tests cover fixed event windows and real SPSC capacities 1/2/4, 64-maker sweeps,
double-queue congestion, notification before waiting, drain and abort. These
tests constrain known cases, not all possible thread schedules. A later measured
waiting-policy experiment belongs to M3, not an extra runtime switch here.
