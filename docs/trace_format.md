# Offline trace format v1

All records are ASCII, whitespace-delimited, decimal integer fields. Writers use
one space between fields and LF after each line. Readers accept CRLF, blank lines
and whole-line comments whose first non-whitespace character is `#`. Inline
comments are not supported. Diagnostics identify the input path and physical
line number, including comments and blank lines; failure to open uses line zero.

The first non-comment record is exactly `LLMATCH_CONFIG 1` for a config file or
`LLMATCH_TRACE 1` for a command trace. Other versions, missing or surplus fields,
unknown commands, truncated values and out-of-range integers fail parsing.
Integers have no leading `+`; unsigned fields cannot have `-`. A trailing token
or character is an error, not ignored input. Zero IDs or quantities, negative
prices and side values 2–255 are representable business inputs and reach engine
validation. Side values above 255 are parse errors. Configuration semantics are
checked by each engine constructor after parsing.

## Configuration

Exactly one data record follows the header:

```text
LLMATCH_CONFIG 1
8 1000 100
```

The fields are `max_live_orders` (size_t), `max_price` (int64),
`max_order_qty` (uint64). Additional data records are errors.

## Commands

Zero or more command records follow the trace header:

```text
LLMATCH_TRACE 1
L 1 1 101 1 100 5
M 2 1 201 0 3
C 1 2 101
```

- `L client request order_id side price qty`: limit order.
- `M client request order_id side qty`: market IOC order.
- `C client request order_id`: cancel the entire active remainder.

Client is uint32; request, order ID and quantity are uint64; price is int64.
Side is uint8, with Buy = 0 and Sell = 1. An empty trace (header only) is valid.

## Events

`write_events` writes one record per event without a separate file header. Each
line starts with `E`, followed by every field in `Event` declaration order:

```text
E kind command_kind command_seq event_seq client request order_id reject_reason cancel_reason completion side price qty arrival_seq maker_id taker_id maker_client taker_client maker_arrival_seq taker_arrival_seq filled_qty resting_qty cancelled_qty
```

The line above names fields; actual records contain only their decimal values.
Enums use their integer encodings from the contract headers. EventKind is
Accepted=0, Rejected=1, Trade=2, Rested=3, Cancelled=4, CommandComplete=5.
CommandKind is Limit=0, Market=1, Cancel=2. Unused fields remain zero/default.
Writers do not localize numbers, even when the destination stream has a locale.

## Snapshots

`write_snapshot` starts each snapshot with `BOOK 1`, then writes the supplied
canonical state in order: bids by descending price, asks by ascending price,
and orders within each level by ascending arrival sequence.

```text
BOOK 1
B 99 5 1
O 10 1 0 99 5 1
A 101 7 2
O 11 2 1 101 3 2
O 12 3 1 101 4 3
```

A level line is `B|A price total_qty order_count`. Each following order line is
`O id owner side price remaining arrival_seq`. Empty books have only the header.
No addresses or container-specific data are serialized. Serialization preserves
the snapshot's ordering; constructing canonical snapshots is the engine's job.

## Input identity

`file_hash` computes FNV-1a 64-bit over the exact raw file bytes (offset basis
14695981039346656037, prime 1099511628211, unsigned wraparound). The result is
`fnv1a64:` plus 16 lowercase hexadecimal digits. Empty input hashes to
`fnv1a64:cbf29ce484222325`; `hello` hashes to `fnv1a64:a430d84680aabd0b`.
Line endings and comments therefore affect the hash. It identifies experiment
inputs and is not a cryptographic integrity or security guarantee.
