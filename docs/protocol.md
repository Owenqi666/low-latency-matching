# M2 TCP protocol, version 1

Each connection carries a sequence of binary frames. All multi-byte integers use
network byte order (big endian). There is no padding, native structure layout,
text encoding, or checksum. Signed prices use a 64-bit two's-complement bit
pattern. Quantities, IDs, and sequence numbers retain their M1 widths.

## Frame header and message types

Every frame begins with this 8-byte header. Offsets in this table are relative to
the start of the frame; all later offsets are relative to the payload.

| Offset | Bytes | Field |
|---:|---:|---|
| 0 | 2 | version, unsigned, must be 1 |
| 2 | 2 | message type, unsigned, listed below |
| 4 | 4 | payload_length, unsigned, excludes the header |

The maximum allowed total frame size is 256 bytes. Each defined type has exactly
one payload length, so this version's largest actual frame is 138 bytes. A
declared payload above 248 bytes is rejected immediately after reading its header;
the receiver does not allocate or wait for that payload.

| Type | Value | Direction | Payload bytes | Frame bytes |
|---|---:|---|---:|---:|
| Welcome | 1 | server to client | 4 | 12 |
| Limit | 2 | client to server | 33 | 41 |
| Market | 3 | client to server | 25 | 33 |
| Cancel | 4 | client to server | 16 | 24 |
| BusinessEvent | 5 | server to client | 130 | 138 |
| Bbo | 6 | server to client | 50 | 58 |

Unknown versions or message types, a mismatched fixed payload length, an oversized
frame, and an incomplete frame at EOF are protocol errors. The Gateway closes
that connection. These failures do not enter Matching or consume business
command/event sequence numbers. A server-to-client type received on the request
path is also a protocol error.

## Welcome and requests

Welcome contains a single unsigned 32-bit ClientId at payload offset 0. Its
protocol version is already in the frame header. The server assigns a nonzero
ClientId for each new connection and does not reuse it during that process's
lifetime. Requests have no ClientId field: Gateway binds the decoded command to
the connection's assigned ID.

| Request field | Offset | Bytes | Type | Present in |
|---|---:|---:|---|---|
| request | 0 | 8 | unsigned RequestId | Limit, Market, Cancel |
| id | 8 | 8 | unsigned OrderId | Limit, Market, Cancel |
| side | 16 | 1 | unsigned Side | Limit, Market |
| price | 17 | 8 | signed Price | Limit |
| qty | 25 | 8 | unsigned Quantity | Limit |
| qty | 17 | 8 | unsigned Quantity | Market |

Side 0 means Buy and 1 means Sell. All other byte values are preserved in requests
for Matching to reject with InvalidSide. The codec likewise preserves zero IDs,
zero quantities, negative prices, and values outside configured business limits;
these are M1 business validation decisions, not malformed frame syntax.
RequestId is correlation data, not an idempotency or deduplication key. Cancel
has no side, price, or quantity.

## BusinessEvent

A BusinessEvent serializes every M1 Event field in declaration order. Unused
fields retain the engine's default zero values; the codec does not infer an
event's fields or reorder them. A single canonical Trade still has one EventSeq
even when the service routes its identical bytes to both participants.

| Field | Offset | Bytes | Type |
|---|---:|---:|---|
| kind | 0 | 1 | EventKind |
| command_kind | 1 | 1 | CommandKind |
| command_seq | 2 | 8 | unsigned Sequence |
| event_seq | 10 | 8 | unsigned Sequence |
| client | 18 | 4 | unsigned ClientId |
| request | 22 | 8 | unsigned RequestId |
| order_id | 30 | 8 | unsigned OrderId |
| reject_reason | 38 | 1 | RejectReason |
| cancel_reason | 39 | 1 | CancelReason |
| completion | 40 | 1 | CompletionStatus |
| side | 41 | 1 | Side |
| price | 42 | 8 | signed Price |
| qty | 50 | 8 | unsigned Quantity |
| arrival_seq | 58 | 8 | unsigned Sequence |
| maker_id | 66 | 8 | unsigned OrderId |
| taker_id | 74 | 8 | unsigned OrderId |
| maker_client | 82 | 4 | unsigned ClientId |
| taker_client | 86 | 4 | unsigned ClientId |
| maker_arrival_seq | 90 | 8 | unsigned Sequence |
| taker_arrival_seq | 98 | 8 | unsigned Sequence |
| filled_qty | 106 | 8 | unsigned Quantity |
| resting_qty | 114 | 8 | unsigned Quantity |
| cancelled_qty | 122 | 8 | unsigned Quantity |

Enum values are fixed by M1:

| Enum | Numeric values |
|---|---|
| EventKind | Accepted=0, Rejected=1, Trade=2, Rested=3, Cancelled=4, CommandComplete=5 |
| CommandKind | Limit=0, Market=1, Cancel=2 |
| RejectReason | None=0, InvalidClientId=1, InvalidRequestId=2, InvalidOrderId=3, InvalidSide=4, InvalidQuantity=5, InvalidPrice=6, DuplicateOrder=7, UnknownOrder=8, NotOwner=9, CapacityExceeded=10 |
| CancelReason | None=0, UserCancel=1, IocRemainder=2 |
| CompletionStatus | None=0, Accepted=1, Rejected=2 |
| Side | Buy=0, Sell=1 |

Response decoders reject values outside these enum ranges. They do not re-run
business validation or check semantic relationships between event fields.
CommandComplete is the terminal result for a processed request; clients must not
treat Accepted or a successful socket write as completion.

## Bbo

The shared C++ value type is llmatch::Bbo. It reports only the best bid/ask and
the aggregate remaining quantity at each best price.

| Field | Offset | Bytes | Type |
|---|---:|---:|---|
| bid_present | 0 | 1 | boolean, 0 or 1 |
| ask_present | 1 | 1 | boolean, 0 or 1 |
| bid_price | 2 | 8 | signed Price |
| bid_qty | 10 | 8 | unsigned Quantity |
| ask_price | 18 | 8 | signed Price |
| ask_qty | 26 | 8 | unsigned Quantity |
| command_seq | 34 | 8 | unsigned Sequence |
| as_of_event_seq | 42 | 8 | unsigned Sequence |

An absent side has presence=false and price=qty=0. An initial empty-book quote
also has both sequence fields zero. A quote caused by a processed command uses
that command's command_seq and its CommandComplete.event_seq minus one as
as_of_event_seq. A Bbo does not allocate another M1 EventSeq.

The service compares presence, best prices, and best quantities after processing
the whole command. If they changed, it sends one final Bbo before that command's
CommandComplete. Intermediate prices during a sweep do not generate Bbo frames.
The default C++ equality operator includes the sequence fields as well, so the
service's change detection must compare quote fields separately. These production
rules belong to the service; the codec only validates the boolean byte syntax.

## C++ framing API

The public header is include/llmatch/protocol.hpp in namespace llmatch::protocol.
Frame owns a fixed 256-byte array and exposes its populated bytes through bytes().
The encode overloads accept Welcome, Command, Event, or llmatch::Bbo and return a
Frame by value. Encoding trusted values requires no heap allocation. Command
encoding deliberately ignores Command.client.

inspect(span) is nonthrowing and examines the first frame only:

- NeedMore with fewer than 8 available bytes reports frame_size=8.
- After a valid complete header, NeedMore reports the expected total frame size.
- Ready reports the first frame's size even if the buffer also contains later
  frames. The caller consumes exactly that prefix and inspects the remainder.
- Invalid reports the reason in error and frame_size=0. Header validation order
  is version, known type, maximum size, then exact type-specific payload length.

decode(span, request_client=0) accepts exactly one complete frame and returns a
variant of Welcome, Command, Event, or llmatch::Bbo. decode_request(span, client)
accepts only Limit, Market, and Cancel and returns Command. Gateway uses the
latter with its assigned ClientId; a caller decoding generic request frames must
also provide that identity explicitly.

Both decoders throw ProtocolError on invalid input. code() exposes Error and
what() exposes a stable name: unsupported_version, unknown_message_type,
invalid_payload_length, frame_too_large, incomplete_frame, trailing_bytes,
unexpected_message_type, or invalid_field. An incomplete buffer is not itself an
error for inspect; calling an exact decoder on it produces incomplete_frame.
At EOF the Gateway treats any unconsumed prefix as a truncated frame.

The codec performs no socket IO, buffering, sequencing, matching, or allocation
based on a wire length. Gateway owns its bounded receive storage and the lifetimes
of encoded frames used by asynchronous writes. TCP read boundaries carry no
message meaning: reads may split the header/payload anywhere or contain multiple
frames.

## Independent Python layout

These standard-library struct formats include no native alignment. Lengths can
be checked with struct.calcsize; the header and payload are packed separately.

| Record | struct format | Bytes |
|---|---|---:|
| Header | !HHI | 8 |
| Welcome | !I | 4 |
| Limit | !QQBqQ | 33 |
| Market | !QQBQ | 25 |
| Cancel | !QQ | 16 |
| BusinessEvent | !BBQQIQQBBBBqQQQQIIQQQQQ | 130 |
| Bbo | !BBqQqQQQ | 50 |

For example, a Cancel with RequestId=2 and OrderId=3 is the following 24 bytes,
written here as hexadecimal groups:

    0001 0004 00000010 0000000000000002 0000000000000003

tests/protocol_test.cpp contains manually specified byte fixtures for all six
types, including every Event field, signed price bytes, and an invalid request
side. It also checks every incomplete prefix, coalesced frames across all chunk
sizes, rejection from header-only input, the exact-decoder error contract, and
decoded invalid requests' rejection precedence through the production engine.
