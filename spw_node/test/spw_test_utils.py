from nmigen.sim import Delay
from bitarray import bitarray
from bitarray.util import int2ba
import math
import sys, os, inspect
from pathlib import Path

LATENCY_BIT_START_TO_STORE_EN = 3
LATENCY_BIT_START_TO_SR_UPDATED = LATENCY_BIT_START_TO_STORE_EN + 1
LATENCY_BIT_START_TO_SYMBOL_DETECTED = LATENCY_BIT_START_TO_SR_UPDATED + 1

def add_module_to_path():
    frame = inspect.stack()[1]
    module = inspect.getmodule(frame[0])
    currentdir = os.path.dirname(os.path.abspath(inspect.getfile(module)))
    parentdir = os.path.dirname(currentdir)
    sys.path.insert(0, parentdir)

def get_gtkw_filename(test_suffix=None):
    return _get_test_output_filename(False, test_suffix)

def get_vcd_filename(test_suffix=None):
    return _get_test_output_filename(True, test_suffix)

def _get_test_output_filename(vcd=True, test_suffix=None):
    frame = inspect.stack()[2]
    active_test_file = inspect.getfile(frame[0])
    module = inspect.getmodule(frame[0])
    currentdir = os.path.dirname(inspect.getfile(module))
    test_prefix = Path(currentdir).stem
    currentdir = os.path.dirname(os.path.abspath(inspect.getfile(module)))
    calframe = inspect.getouterframes(inspect.currentframe(), 2)
    test_prefix_2 = calframe[2][3]

    extension = '.vcd' if vcd else '.gtkw'
    folder = 'vcd' if vcd else 'gtkw'
    filename = os.path.join(currentdir, folder, '_'.join([test_prefix, test_prefix_2]))
    filename = '_'.join([filename, test_suffix]) + extension if test_suffix else filename + extension

    return filename

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

def ds_sim_send_d(i_d, i_s, d, bit_time=0.5e-6):
    global prev_d
    global prev_s
    yield i_d.eq(d)
    if d != prev_d:
        yield i_s.eq(prev_s)
    else:
        prev_s = not prev_s
        yield i_s.eq(prev_s)
    prev_d = d
    yield Delay(bit_time)

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

def ds_sim_send_null(i_d, i_s, bit_time=0.5e-6):
    global prev_parity
    parity = not (prev_parity ^ True)
    prev_parity = False
    yield from ds_sim_send_d(i_d, i_s, parity, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, bit_time)
    parity = not (prev_parity ^ True)
    prev_parity = False
    yield from ds_sim_send_d(i_d, i_s, parity, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 0, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 0, bit_time)

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
