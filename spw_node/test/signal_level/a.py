from nmigen import *
from nmigen.sim import Simulator, Delay, Settle
from spw_node.src.spw_receiver import SpWReceiver
from spw_node.test.spw_test_utils import (
    ds_sim_send_d, get_vcd_filename, get_gtkw_filename,
    ds_sim_send_null
)

def test_6_3_2_a():

    SRCFREQ = 10e6
    SIMSTART = 20e-6
    BIT_TIME = 0.5e-6
    CHAR_TIME = BIT_TIME * 4
    LATENCY_BIT_START_TO_STORE_EN = 3
    LATENCY_BIT_START_TO_SR_UPDATED = LATENCY_BIT_START_TO_STORE_EN + 1
    LATENCY_BIT_START_TO_SYMBOL_DETECTED = LATENCY_BIT_START_TO_SR_UPDATED + 1

    dut = SpWReceiver(SRCFREQ, 1)

    sim = Simulator(dut)
    sim.add_clock(1/SRCFREQ)

    def ds_send_simultaneous():
        yield from ds_sim_send_d(dut.i_d, dut.i_s, 0, BIT_TIME)
        yield from ds_sim_send_d(dut.i_d, dut.i_s, 1, BIT_TIME)
        yield from ds_sim_send_d(dut.i_d, dut.i_s, 1, BIT_TIME)
        yield from ds_sim_send_d(dut.i_d, dut.i_s, 1, BIT_TIME)
        yield dut.i_d.eq(0)
        yield dut.i_s.eq(0)
        yield Delay(BIT_TIME)
        yield from ds_sim_send_d(dut.i_d, dut.i_s, 1, BIT_TIME)
        yield from ds_sim_send_d(dut.i_d, dut.i_s, 0, BIT_TIME)
        yield from ds_sim_send_d(dut.i_d, dut.i_s, 0, BIT_TIME)

    def ds_input():
        yield dut.i_s.eq(0)
        yield dut.i_d.eq(0)
        yield Delay(SIMSTART)
        yield from ds_sim_send_null(dut.i_d, dut.i_s, BIT_TIME)
        yield from ds_sim_send_null(dut.i_d, dut.i_s, BIT_TIME)
        yield from ds_send_simultaneous()
        yield from ds_sim_send_null(dut.i_d, dut.i_s, BIT_TIME)
        yield from ds_sim_send_null(dut.i_d, dut.i_s, BIT_TIME)
        yield from ds_sim_send_null(dut.i_d, dut.i_s, BIT_TIME)
        yield from ds_send_simultaneous()
        yield from ds_sim_send_null(dut.i_d, dut.i_s, BIT_TIME)
        yield from ds_sim_send_null(dut.i_d, dut.i_s, BIT_TIME)
        yield from ds_sim_send_null(dut.i_d, dut.i_s, BIT_TIME)

    def validate_symbol_received(s):
        yield Delay(BIT_TIME * 2)
        for _ in range(LATENCY_BIT_START_TO_SYMBOL_DETECTED):
            yield
        yield Settle()
        assert (yield s)

    def test_first_esc():
        yield Delay(SIMSTART)
        yield Delay(CHAR_TIME)
        yield from validate_symbol_received(dut.o_got_esc)

    def test_first_null():
        yield Delay(SIMSTART)
        yield Delay(CHAR_TIME)
        yield Delay(CHAR_TIME)
        yield from validate_symbol_received(dut.o_got_null)

    def test_null_after_simultaneous_1():
        yield Delay(SIMSTART)
        yield Delay(CHAR_TIME * 10)
        yield from validate_symbol_received(dut.o_got_null)

    def test_null_after_simultaneous_2():
        yield Delay(SIMSTART)
        yield Delay(CHAR_TIME * 18)
        yield from validate_symbol_received(dut.o_got_null)

    def reset_on_error():
        while True:
            if (yield dut.o_parity_error):
                yield dut.i_reset.eq(1)
                yield
                yield dut.i_reset.eq(0)
                yield
            else:
                yield

    sim.add_process(ds_input)
    sim.add_sync_process(reset_on_error)
    sim.add_sync_process(test_first_esc)
    sim.add_sync_process(test_null_after_simultaneous_1)
    sim.add_sync_process(test_null_after_simultaneous_2)

    with sim.write_vcd(get_vcd_filename(), get_gtkw_filename(), traces=dut.ports()):
        sim.run_until(50e-6)
