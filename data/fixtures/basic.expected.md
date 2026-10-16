# Hand-calculated fixture: C=8, max_price=102, max_order_qty=100

Sequence counters start at zero. Each row is one command; event IDs are explicit.
`A`=Accepted, `T`=Trade, `R`=Rested, `X`=Cancelled, `J`=Rejected, `D`=Complete.
Trade identifies maker/taker IDs; its clients and arrival sequences are the
corresponding submitting command's client and command sequence. Every event has
the current command's client/request/target; unused fields are zero/default.

| Command (client, request) | Full event order | Complete (filled, resting, cancelled) | Snapshot asks (FIFO); bids empty |
|---|---|---|---|
| 1: (1,1) sell limit 101 100x5 | 1 A; 2 R(101,Sell,100,5,arrival=1); 3 D(Accepted) | 0,5,0 | 100 total5: 101 owner1 qty5 seq1 |
| 2: (2,1) sell limit 102 100x7 | 4 A; 5 R(102,Sell,100,7,arrival=2); 6 D(Accepted) | 0,7,0 | 100 total12: 101(5,1),102(7,2) |
| 3: (3,1) buy limit 201 101x8 | 7 A; 8 T(101/201,5@100); 9 T(102/201,3@100); 10 D(Accepted) | 8,0,0 | 100 total4: 102 owner2 qty4 seq2 |
| 4: (2,2) sell limit 103 99x2 | 11 A; 12 R(103,Sell,99,2,arrival=4); 13 D(Accepted) | 0,2,0 | 99 total2:103 owner2 qty2 seq4; 100 total4:102(4,2) |
| 5: (4,1) buy market 202 qty5 | 14 A; 15 T(103/202,2@99); 16 T(102/202,3@100); 17 D(Accepted) | 5,0,0 | 100 total1:102 owner2 qty1 seq2 |
| 6: (2,3) cancel 102 | 18 A; 19 X(102,1,UserCancel); 20 D(Accepted) | 0,0,1 | empty |
| 7: (3,2) buy market 203 qty4 | 21 A; 22 X(203,4,IocRemainder); 23 D(Accepted) | 0,0,4 | empty |
| 8: (2,4) cancel 102 | 24 J(UnknownOrder); 25 D(Rejected) | 0,0,0 | empty |

Independent C=1 case: (1,1) sell limit301 100x5 -> events 1 A, 2 R,
3 D(0,5,0); (2,1) buy limit302 101x5 -> 4 J(CapacityExceeded),
5 D(Rejected,0,0,0), book unchanged; (2,2) buy market303 qty5 -> 6 A,
7 T(301/303,5@100), 8 D(Accepted,5,0,0), book empty.

Additional independent fixture expectations: non-owner cancel returns NotOwner
with unchanged state; reverse-side makers execute highest bid first at maker
price; invalid configuration throws before use; insufficient output leaves all
bytes and state unchanged; sequence exhaustion leaves counters and state unchanged.
