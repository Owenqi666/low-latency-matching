#!/usr/bin/env python3
"""Independent, deliberately simple ITCH 5.0 BinaryFILE reconstruction.

The only persistent book is an order dictionary. Levels and BBO are calculated
directly from its contents, independently of the C++ aggregate implementation.
"""
from collections import Counter
from pathlib import Path

LENGTHS = dict(S=12, R=39, A=36, F=40, E=31, C=36, X=23, D=19, U=35,
               H=25, Y=20, L=26, V=35, W=12, K=28, J=35, h=21,
               P=44, Q=40, B=19, I=50, N=20, O=48)
IGNORED = set('H Y L V W K J h P Q B I N O'.split())
UPDATES = set('AFECXDU')
PRICE_MAX = 2_000_000_000
DAY_NS = 86_400_000_000_000


class ItchError(ValueError):
    def __init__(self, message, offset=None, message_index=None, kind=None, reference=None):
        super().__init__(message)
        self.details = {'error': message}
        for key, value in [('offset', offset), ('message_index', message_index),
                           ('type', kind), ('reference', reference)]:
            if value is not None:
                self.details[key] = value


def uint(data, start, size):
    return int.from_bytes(data[start:start + size], 'big')


def ascii_field(data):
    if any(value < 32 or value > 126 for value in data):
        raise ValueError('non-printable ASCII field')
    return data.decode('ascii').rstrip(' ')


def decode(payload, offset=0, message_index=1):
    """Read wire fields, without assuming that non-target orders are valid."""
    kind = chr(payload[0]) if payload else ''
    if kind not in LENGTHS:
        raise ItchError('unknown message type', offset, message_index, kind)
    if len(payload) != LENGTHS[kind]:
        raise ItchError('wrong message length', offset, message_index, kind)
    result = dict(type=kind, locate=uint(payload, 1, 2), tracking=uint(payload, 3, 2),
                  timestamp=uint(payload, 5, 6), offset=offset, message_index=message_index)
    if result['timestamp'] >= DAY_NS:
        raise ItchError('timestamp outside trading day', offset, message_index, kind)
    if kind == 'S':
        result['event'] = chr(payload[11])
    elif kind == 'R':
        result['stock_bytes'] = payload[11:19]
    elif kind in 'AF':
        result.update(reference=uint(payload, 11, 8), side=chr(payload[19]),
                      shares=uint(payload, 20, 4), stock_bytes=payload[24:32],
                      price=uint(payload, 32, 4),
                      attribution_bytes=payload[36:40] if kind == 'F' else b'')
    elif kind in 'ECXD':
        result['reference'] = uint(payload, 11, 8)
        if kind != 'D':
            result['shares'] = uint(payload, 19, 4)
        if kind == 'C':
            result.update(printable=chr(payload[31]), price=uint(payload, 32, 4))
    elif kind == 'U':
        result.update(reference=uint(payload, 11, 8), new_reference=uint(payload, 19, 8),
                      shares=uint(payload, 27, 4), price=uint(payload, 31, 4))
    return result


def level_key(level):
    return (0, -level['price']) if level['side'] == 'B' else (1, level['price'])


class Reference:
    def __init__(self, symbol, max_orders=1_000_000):
        self.symbol, self.max_orders = symbol, max_orders
        self.orders = {}
        self.locate = None
        self.directories = {}
        self.counts, self.ignored = Counter(), Counter()
        self.messages = self.target_messages = self.filtered = self.updates = 0
        self.events = ''

    def levels(self):
        totals = {}
        for order in self.orders.values():
            key = order['side'], order['price']
            level = totals.setdefault(key, dict(side=key[0], price=key[1], shares=0, orders=0))
            level['shares'] += order['shares']
            level['orders'] += 1
            if level['shares'] > (1 << 64) - 1:
                raise ValueError('aggregate shares overflow')
        return sorted(totals.values(), key=level_key)

    def snapshot(self):
        return dict(orders=[self.orders[ref].copy() for ref in sorted(self.orders)], levels=self.levels())

    @staticmethod
    def bbo(levels):
        return dict(bid=next((x for x in levels if x['side'] == 'B'), None),
                    ask=next((x for x in levels if x['side'] == 'S'), None))

    def apply(self, msg):
        kind = msg['type']
        def fail(reason, ref=None):
            raise ItchError(reason, msg['offset'], msg['message_index'], kind, ref)
        if self.events.endswith('C'):
            fail('message after End of Messages')
        if self.messages == 0 and (kind != 'S' or msg['event'] != 'O'):
            fail('session must start with S/O')
        self.messages += 1
        self.counts[kind] += 1
        if kind == 'S':
            event = msg['event']
            if msg['locate'] != 0 or event not in 'OSQMEC' or (event == 'O' and self.events):
                fail('invalid system event')
            self.events += event
            return None
        if kind == 'R':
            try:
                stock = ascii_field(msg['stock_bytes'])
            except ValueError as error:
                fail(str(error))
            if not stock:
                fail('empty directory stock')
            if stock == self.symbol:
                if not msg['locate'] or (self.locate is not None and self.locate != msg['locate']):
                    fail('target stock locate conflict')
                if msg['locate'] in self.directories and self.directories[msg['locate']] != stock:
                    fail('target stock locate conflict')
                self.locate = msg['locate']
            elif self.locate == msg['locate']:
                fail('target stock locate conflict')
            self.directories[msg['locate']] = stock
        if kind in 'AF' and msg['stock_bytes'] == self.symbol.encode().ljust(8, b' '):
            if self.locate is None or msg['locate'] != self.locate:
                fail('target add has no matching directory', msg['reference'])
        target = self.locate is not None and msg['locate'] == self.locate
        if target:
            self.target_messages += 1
        else:
            self.filtered += 1
        if kind in IGNORED:
            self.ignored[kind] += 1
            return None
        if not target or kind == 'R':
            return None
        ref = msg['reference']
        if kind in 'AF':
            try:
                stock = ascii_field(msg['stock_bytes'])
                attribution = ascii_field(msg['attribution_bytes'])
            except ValueError as error:
                fail(str(error), ref)
            if stock != self.symbol or msg['side'] not in 'BS' or msg['side'] == '':
                fail('invalid target add fields', ref)
            if not msg['shares'] or msg['price'] > PRICE_MAX:
                fail('invalid shares or price', ref)
            if ref in self.orders:
                fail('duplicate active reference', ref)
            if len(self.orders) >= self.max_orders:
                fail('active order capacity reached', ref)
            affected_refs = {ref}
            affected_levels = {(msg['side'], msg['price'])}
            new_order = dict(reference=ref, side=msg['side'], price=msg['price'],
                             shares=msg['shares'], attribution=attribution)
            self.orders[ref] = new_order
        else:
            if ref not in self.orders:
                fail('unknown target order reference', ref)
            old = self.orders[ref]
            affected_refs = {ref}
            affected_levels = {(old['side'], old['price'])}
            if kind == 'U':
                new_ref = msg['new_reference']
                if new_ref in self.orders:
                    fail('replacement reference conflict', new_ref)
                if not msg['shares'] or msg['price'] > PRICE_MAX:
                    fail('invalid replacement shares or price', ref)
                new = dict(old, reference=new_ref, shares=msg['shares'], price=msg['price'])
                affected_refs.add(new_ref)
                affected_levels.add((new['side'], new['price']))
                del self.orders[ref]
                self.orders[new_ref] = new
            elif kind == 'D':
                del self.orders[ref]
            else:
                if not 0 < msg['shares'] <= old['shares']:
                    fail('invalid decrement shares', ref)
                if kind == 'C' and (msg['printable'] not in ('Y', 'N') or msg['price'] > PRICE_MAX):
                    fail('invalid execution fields', ref)
                left = old['shares'] - msg['shares']
                if left:
                    self.orders[ref] = dict(old, shares=left)
                else:
                    del self.orders[ref]
        self.updates += 1
        levels = self.levels()
        lookup = {(x['side'], x['price']): x for x in levels}
        touched = [lookup.get(key, dict(side=key[0], price=key[1], shares=0, orders=0))
                   for key in affected_levels]
        return dict(kind='update', message_index=self.messages, offset=msg['offset'], type=kind,
                    update_index=self.updates,
                    orders=[dict(reference=r, state=self.orders[r].copy() if r in self.orders else None)
                            for r in sorted(affected_refs)], levels=sorted(touched, key=level_key),
                    bbo=self.bbo(levels), active_orders=len(self.orders))


def replay(path, symbol, prefix=False, max_orders=1_000_000, checkpoint_every=10_000):
    """Yield expected audit records directly from original BinaryFILE bytes."""
    model = Reference(symbol, max_orders)
    offset = last_offset = 0
    ended = False
    fnv = 14695981039346656037
    def hash_bytes(data):
        nonlocal fnv
        for byte in data:
            fnv = ((fnv ^ byte) * 1099511628211) & ((1 << 64) - 1)
    with Path(path).open('rb') as stream:
        while True:
            header = stream.read(2)
            if not header:
                break
            hash_bytes(header)
            last_offset = offset
            if len(header) != 2:
                raise ItchError('truncated frame length', offset, model.messages + 1)
            size = int.from_bytes(header, 'big')
            if size == 0:
                offset += 2
                ended = True
                if stream.read(1):
                    raise ItchError('bytes after binary terminator', offset, model.messages + 1)
                break
            payload = stream.read(size)
            hash_bytes(payload)
            if len(payload) != size:
                raise ItchError('truncated frame payload', offset, model.messages + 1)
            record = model.apply(decode(payload, offset, model.messages + 1))
            offset += size + 2
            if record:
                yield record
                if model.updates % checkpoint_every == 0:
                    yield dict(kind='checkpoint', message_index=model.messages,
                               update_index=model.updates, **model.snapshot())
    itch_end = model.events.endswith('C')
    if (not prefix and not (ended and itch_end)) or (ended and not itch_end):
        raise ItchError('complete input requires S/C and binary terminator', last_offset, model.messages)
    if model.locate is None or not model.updates:
        raise ItchError('no target directory or target updates', last_offset, model.messages)
    snapshot = model.snapshot()
    summary = dict(schema_version=1, status='passed', symbol=symbol, stock_locate=model.locate,
                   prefix_allowed=prefix, session_complete=ended and itch_end,
                   binary_end=ended, itch_end=itch_end, bytes=offset, last_offset=last_offset,
                   messages=model.messages, target_messages=model.target_messages, updates=model.updates,
                   filtered_messages=model.filtered, counts_by_type=dict(model.counts),
                   ignored_by_type=dict(model.ignored), system_events=model.events,
                   active_orders=len(model.orders), bbo=model.bbo(snapshot['levels']),
                   input_fnv1a64=f'{fnv:016x}')
    yield dict(kind='final', summary=summary, **snapshot)
