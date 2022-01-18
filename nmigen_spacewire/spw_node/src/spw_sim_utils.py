from amaranth.sim import Delay
from bitarray import bitarray
from bitarray.util import int2ba
import math

global prev_d
global prev_s
global prev_parity
prev_d = False
prev_s = False
prev_parity = False

def ds_sim_char_to_bits(c):
    ret = bitarray(endian='little')
    ret.frombytes(c.encode())
    return ret

def ds_sim_period_to_ticks(p, srcfreq):
    return math.ceil(p * srcfreq)

def ds_sim_send_d(i_d, i_s, d):
    global prev_d
    global prev_s
    yield i_d.eq(d)
    if d != prev_d:
        yield i_s.eq(prev_s)
    else:
        prev_s = not prev_s
        yield i_s.eq(prev_s)
    prev_d = d
    yield Delay(0.5e-6)

def ds_sim_send_char(i_d, i_s, b):
    global prev_parity
    data = bitarray(endian='little')
    data.frombytes(b.encode())
    parity = not (prev_parity ^ False)
    next_parity = False
    for i in range(8):
        next_parity = next_parity ^ data[i]
    prev_parity = next_parity
    yield from ds_sim_send_d(i_d, i_s, parity)
    yield from ds_sim_send_d(i_d, i_s, 0)
    for i in range(8):
        yield from ds_sim_send_d(i_d, i_s, data[i])

def ds_sim_send_int(i_d, i_s, b):
    global prev_parity
    data = int2ba(b, length=8, endian='little')
    parity = not (prev_parity ^ False)
    next_parity = False
    for i in range(8):
        next_parity = next_parity ^ data[i]
    prev_parity = next_parity
    yield from ds_sim_send_d(i_d, i_s, parity)
    yield from ds_sim_send_d(i_d, i_s, 0)
    for i in range(8):
        yield from ds_sim_send_d(i_d, i_s, data[i])

def ds_sim_send_null(i_d, i_s):
    global prev_parity
    parity = not (prev_parity ^ True)
    prev_parity = False
    yield from ds_sim_send_d(i_d, i_s, parity)
    yield from ds_sim_send_d(i_d, i_s, 1)
    yield from ds_sim_send_d(i_d, i_s, 1)
    yield from ds_sim_send_d(i_d, i_s, 1)
    parity = not (prev_parity ^ True)
    prev_parity = False
    yield from ds_sim_send_d(i_d, i_s, parity)
    yield from ds_sim_send_d(i_d, i_s, 1)
    yield from ds_sim_send_d(i_d, i_s, 0)
    yield from ds_sim_send_d(i_d, i_s, 0)

def ds_sim_send_timecode(i_d, i_s, code):
    global prev_parity
    parity = not (prev_parity ^ True)
    prev_parity = False
    yield from ds_sim_send_d(i_d, i_s, parity)
    yield from ds_sim_send_d(i_d, i_s, 1)
    yield from ds_sim_send_d(i_d, i_s, 1)
    yield from ds_sim_send_d(i_d, i_s, 1)
    yield from ds_sim_send_int(i_d, i_s, code)

def ds_sim_send_wrong_null(i_d, i_s):
    global prev_parity
    parity = not (prev_parity ^ True)
    prev_parity = False
    yield from ds_sim_send_d(i_d, i_s, parity)
    yield from ds_sim_send_d(i_d, i_s, 1)
    yield from ds_sim_send_d(i_d, i_s, 1)
    yield from ds_sim_send_d(i_d, i_s, 1)
    parity = not (prev_parity ^ True)
    prev_parity = False
    yield from ds_sim_send_d(i_d, i_s, not parity)
    yield from ds_sim_send_d(i_d, i_s, 1)
    yield from ds_sim_send_d(i_d, i_s, 0)
    yield from ds_sim_send_d(i_d, i_s, 0)
