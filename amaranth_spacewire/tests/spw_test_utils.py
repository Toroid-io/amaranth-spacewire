import math
import os
import inspect

from amaranth.sim import Delay, Settle, Tick
from bitarray import bitarray
from bitarray.util import int2ba
from pathlib import Path

# TODO: Please document these
LATENCY_FF_SYNCHRONIZER = 2
LATENCY_BIT_START_TO_STORE_EN = LATENCY_FF_SYNCHRONIZER + 3
LATENCY_BIT_START_TO_SR_UPDATED = LATENCY_BIT_START_TO_STORE_EN + 1
LATENCY_BIT_START_TO_SYMBOL_DETECTED = LATENCY_BIT_START_TO_SR_UPDATED + 1

def get_gtkw_filename(test_suffix=None):
    return _get_test_output_filename('gtkw', test_suffix)

def get_vcd_filename(test_suffix=None):
    return _get_test_output_filename('vcd', test_suffix)

def get_il_filename(test_suffix=None):
    return _get_test_output_filename('il', test_suffix)

def _get_test_output_filename(extension='vcd', test_suffix=None):
    frame = inspect.stack()[2]
    active_test_file = inspect.getfile(frame[0])
    module = inspect.getmodule(frame[0])
    currentdir = os.path.dirname(inspect.getfile(module))
    test_prefix = Path(currentdir).stem
    currentdir = os.path.dirname(os.path.abspath(inspect.getfile(module)))
    calframe = inspect.getouterframes(inspect.currentframe(), 2)
    test_prefix_2 = calframe[2][3]

    folder = extension
    extension = '.'+extension
    filename = os.path.join(currentdir, folder, '_'.join([test_prefix, test_prefix_2]))
    filename = '_'.join([filename, test_suffix]) + extension if test_suffix else filename + extension

    return filename

def create_sim_output_dirs(vcd_dir, gtkw_dir):
    try:
        os.makedirs(os.path.dirname(vcd_dir))
    except FileExistsError:
        pass

    try:
        os.makedirs(os.path.dirname(gtkw_dir))
    except FileExistsError:
        pass

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
    return math.floor(p * srcfreq)

def ds_sim_delay(p, srcfreq):
    for _ in range(ds_sim_period_to_ticks(p, srcfreq)):
        yield Tick()

def ds_round_bit_time(bit_freq_in, src_freq):
    return ds_sim_period_to_ticks(1/bit_freq_in, src_freq) / src_freq

def ds_sim_send_d(i_d, i_s, d, src_freq, bit_time):
    global prev_d
    global prev_s
    yield i_d.eq(d)
    if d != prev_d:
        yield i_s.eq(prev_s)
    else:
        prev_s = not prev_s
        yield i_s.eq(prev_s)
    prev_d = d
    yield from ds_sim_delay(bit_time, src_freq)

def ds_sim_send_char(i_d, i_s, b, src_freq, bit_time):
    global prev_parity
    data = bitarray(endian='little')
    data.frombytes(b.encode())
    parity = not (prev_parity ^ False)
    next_parity = False
    for i in range(8):
        next_parity = next_parity ^ data[i]
    prev_parity = next_parity
    yield from ds_sim_send_d(i_d, i_s, parity, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 0, src_freq, bit_time)
    for i in range(8):
        yield from ds_sim_send_d(i_d, i_s, data[i], src_freq, bit_time)

def ds_sim_send_int(i_d, i_s, b, src_freq):
    global prev_parity
    data = int2ba(b, length=8, endian='little')
    parity = not (prev_parity ^ False)
    next_parity = False
    for i in range(8):
        next_parity = next_parity ^ data[i]
    prev_parity = next_parity
    yield from ds_sim_send_d(i_d, i_s, parity, src_freq)
    yield from ds_sim_send_d(i_d, i_s, 0, src_freq)
    for i in range(8):
        yield from ds_sim_send_d(i_d, i_s, data[i], src_freq)

def ds_sim_send_null(i_d, i_s, src_freq, bit_time):
    global prev_parity
    parity = not (prev_parity ^ True)
    prev_parity = False
    yield from ds_sim_send_d(i_d, i_s, parity, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)
    parity = not (prev_parity ^ True)
    prev_parity = False
    yield from ds_sim_send_d(i_d, i_s, parity, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 0, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 0, src_freq, bit_time)

def ds_sim_send_fct(i_d, i_s, src_freq, bit_time):
    global prev_parity
    parity = not (prev_parity ^ True)
    prev_parity = False
    yield from ds_sim_send_d(i_d, i_s, parity, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 0, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 0, src_freq, bit_time)

def ds_sim_send_esc(i_d, i_s, src_freq, bit_time):
    global prev_parity
    parity = not (prev_parity ^ True)
    prev_parity = False
    yield from ds_sim_send_d(i_d, i_s, parity, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)

def ds_sim_send_eop(i_d, i_s, src_freq, bit_time):
    global prev_parity
    parity = not (prev_parity ^ True)
    prev_parity = True
    yield from ds_sim_send_d(i_d, i_s, parity, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 0, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)

def ds_sim_send_eep(i_d, i_s, src_freq, bit_time):
    global prev_parity
    parity = not (prev_parity ^ True)
    prev_parity = True
    yield from ds_sim_send_d(i_d, i_s, parity, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 0, src_freq, bit_time)

def ds_sim_send_timecode(i_d, i_s, code, src_freq):
    global prev_parity
    parity = not (prev_parity ^ True)
    prev_parity = False
    yield from ds_sim_send_d(i_d, i_s, parity, src_freq)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq)
    yield from ds_sim_send_int(i_d, i_s, code, src_freq)

def ds_sim_send_wrong_null(i_d, i_s, src_freq, bit_time):
    global prev_parity
    parity = not (prev_parity ^ True)
    prev_parity = False
    yield from ds_sim_send_d(i_d, i_s, parity, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)
    parity = not (prev_parity ^ True)
    prev_parity = False
    yield from ds_sim_send_d(i_d, i_s, not parity, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 1, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 0, src_freq, bit_time)
    yield from ds_sim_send_d(i_d, i_s, 0, src_freq, bit_time)

def validate_symbol_received(src_freq, bit_time, s):
    # Wait for parity bit to arrive
    # Parity is in the next symbol's first two bytes and includes symbol type,
    # so wait for two bit times
    # We could be one Tick off in the detection chain, so test exact deadline +/- 1 Tick
    waited = LATENCY_BIT_START_TO_SYMBOL_DETECTED - 1
    yield from ds_sim_delay(2 * bit_time, src_freq)
    for _ in range(LATENCY_BIT_START_TO_SYMBOL_DETECTED - 1):
        yield Tick()
    yield Settle()

    if ((yield s) == 0):
        waited = waited + 1
        yield Tick()
        yield Settle()

    if ((yield s) == 0):
        waited = waited + 1
        yield Tick()
        yield Settle()
        assert((yield s))

    return bit_time * 2 + (waited) * (1/src_freq)

def validate_multiple_symbol_received(src_freq, bit_time, s, num):
    total_waited = 0
    waited = 0
    for i in range(num):
        yield from ds_sim_delay(2 * 4 * bit_time - waited, src_freq)
        waited = yield from validate_symbol_received(src_freq, bit_time, s)
        total_waited = total_waited + waited

    return total_waited
