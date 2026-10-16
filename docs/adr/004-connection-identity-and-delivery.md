# ADR 004: process-local connection identity and explicit delivery loss

Status: implemented; network acceptance in progress.

Each TCP connection receives a fresh nonzero ClientId from the server. Requests
cannot claim another identity. Active OrderId ownership and RequestId's
non-deduplicating correlation semantics remain the M1 contract. Reusing a socket
descriptor cannot transfer old ownership. Trade carries both owners and is routed
to both, with one copy for self-trades.

Disconnect retains admitted commands and resting orders. This keeps connection
timing out of matching rules and permits deterministic replay of the admitted
trace. The cost is explicit: a new connection cannot cancel its previous
connection's orders. There is no authentication, session recovery or replay of
missed results. Restart clears all state.

Each peer has its own outgoing-byte budget, including active writes. Exhaustion
closes that peer with a reason and counts unsent frames; results for a closed
identity continue to be consumed and counted. Healthy clients can continue. We
do not silently drop business events while claiming complete delivery.

Normal shutdown drains admitted work and has a finite write deadline. Publication,
Gateway consumption, local write completion and client receipt are different
observations. Failure/timeout remains a failed service run even when a test
intentionally expects that outcome. Recovery or persisted acknowledgements would
require a separate milestone and delivery contract.
