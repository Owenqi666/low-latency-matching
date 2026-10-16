#pragma once
#include "llmatch/event.hpp"
#include "llmatch/snapshot.hpp"
#include <vector>

namespace fixtures {
using namespace llmatch;
struct Step { Command command; std::vector<Event> events; BookSnapshot snapshot; };
inline Event event(EventKind kind, const Command& command, Sequence cs, Sequence es) {
    Event value{};
    value.kind = kind; value.command_kind = command_kind(command);
    value.command_seq = cs; value.event_seq = es; value.client = command.client;
    value.request = command.request; value.order_id = order_id(command);
    return value;
}
inline Event complete(const Command& c, Sequence cs, Sequence es, Quantity fill,
                      Quantity rest, Quantity cancel, bool accepted = true) {
    auto e = event(EventKind::CommandComplete, c, cs, es);
    e.completion = accepted ? CompletionStatus::Accepted : CompletionStatus::Rejected;
    e.filled_qty = fill; e.resting_qty = rest; e.cancelled_qty = cancel;
    return e;
}
inline Event rested(const Command& c, Sequence cs, Sequence es, Side side, Price price, Quantity qty) {
    auto e = event(EventKind::Rested, c, cs, es);
    e.side = side; e.price = price; e.qty = qty; e.arrival_seq = cs;
    return e;
}
inline Event trade(const Command& c, Sequence cs, Sequence es, OrderId maker,
                   ClientId owner, Sequence arrival, Price price, Quantity qty) {
    auto e = event(EventKind::Trade, c, cs, es);
    e.maker_id = maker; e.taker_id = order_id(c); e.maker_client = owner;
    e.taker_client = c.client; e.maker_arrival_seq = arrival; e.taker_arrival_seq = cs;
    e.price = price; e.qty = qty;
    return e;
}
inline Event cancelled(const Command& c, Sequence cs, Sequence es, Quantity qty, CancelReason reason) {
    auto e = event(EventKind::Cancelled, c, cs, es); e.qty = qty; e.cancel_reason = reason;
    return e;
}
inline Event rejected(const Command& c, Sequence cs, Sequence es, RejectReason reason) {
    auto e = event(EventKind::Rejected, c, cs, es); e.reject_reason = reason; return e;
}
inline std::vector<Step> basic() {
    const Command c1{1,1,LimitOrder{101,Side::Sell,100,5}};
    const Command c2{2,1,LimitOrder{102,Side::Sell,100,7}};
    const Command c3{3,1,LimitOrder{201,Side::Buy,101,8}};
    const Command c4{2,2,LimitOrder{103,Side::Sell,99,2}};
    const Command c5{4,1,MarketOrder{202,Side::Buy,5}};
    const Command c6{2,3,CancelOrder{102}};
    const Command c7{3,2,MarketOrder{203,Side::Buy,4}};
    const Command c8{2,4,CancelOrder{102}};
    return {
        {c1,{event(EventKind::Accepted,c1,1,1),rested(c1,1,2,Side::Sell,100,5),complete(c1,1,3,0,5,0)},
            {{},{{100,5,{{101,1,Side::Sell,100,5,1}}}}}},
        {c2,{event(EventKind::Accepted,c2,2,4),rested(c2,2,5,Side::Sell,100,7),complete(c2,2,6,0,7,0)},
            {{},{{100,12,{{101,1,Side::Sell,100,5,1},{102,2,Side::Sell,100,7,2}}}}}},
        {c3,{event(EventKind::Accepted,c3,3,7),trade(c3,3,8,101,1,1,100,5),trade(c3,3,9,102,2,2,100,3),complete(c3,3,10,8,0,0)},
            {{},{{100,4,{{102,2,Side::Sell,100,4,2}}}}}},
        {c4,{event(EventKind::Accepted,c4,4,11),rested(c4,4,12,Side::Sell,99,2),complete(c4,4,13,0,2,0)},
            {{},{{99,2,{{103,2,Side::Sell,99,2,4}}},{100,4,{{102,2,Side::Sell,100,4,2}}}}}},
        {c5,{event(EventKind::Accepted,c5,5,14),trade(c5,5,15,103,2,4,99,2),trade(c5,5,16,102,2,2,100,3),complete(c5,5,17,5,0,0)},
            {{},{{100,1,{{102,2,Side::Sell,100,1,2}}}}}},
        {c6,{event(EventKind::Accepted,c6,6,18),cancelled(c6,6,19,1,CancelReason::UserCancel),complete(c6,6,20,0,0,1)},{}},
        {c7,{event(EventKind::Accepted,c7,7,21),cancelled(c7,7,22,4,CancelReason::IocRemainder),complete(c7,7,23,0,0,4)},{}},
        {c8,{rejected(c8,8,24,RejectReason::UnknownOrder),complete(c8,8,25,0,0,0,false)},{}},
    };
}
}
