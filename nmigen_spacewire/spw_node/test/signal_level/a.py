from amaranth import *
from amaranth.sim import Simulator, Delay, Settle
from spw_node.src.spw_node import SpWNode, SpWNodeFSMStates
from spw_node.test.spw_test_utils import *

def test_6_3_2_a():

    SRCFREQ = 20e6
    SIMSTART = 20e-6
    # Use reset frequency to avoid managing two frequencies
    TX_FREQ = 10e6
    BIT_TIME = 1/TX_FREQ
    CHAR_TIME = BIT_TIME * 4

    dut = SpWNode(srcfreq=SRCFREQ, txfreq=TX_FREQ, disconnect_delay=1, debug=True)

    sim = Simulator(dut)
    sim.add_clock(1/SRCFREQ)

    def init():
        yield dut.link_disabled.eq(0)
        yield dut.link_start.eq(1)
        yield dut.autostart.eq(1)
        yield dut.r_en.eq(0)
        yield dut.soft_reset.eq(0)
        yield dut.tick_input.eq(0)
        yield dut.w_en.eq(0)
        yield Settle()

    def ds_send_simultaneous():
        yield from ds_sim_send_d(dut.d_input, dut.s_input, 0, BIT_TIME)
        yield from ds_sim_send_d(dut.d_input, dut.s_input, 1, BIT_TIME)
        yield from ds_sim_send_d(dut.d_input, dut.s_input, 1, BIT_TIME)
        yield from ds_sim_send_d(dut.d_input, dut.s_input, 1, BIT_TIME)
        yield dut.d_input.eq(0)
        yield dut.s_input.eq(0)
        yield Delay(BIT_TIME)
        yield from ds_sim_send_d(dut.d_input, dut.s_input, 1, BIT_TIME)
        yield from ds_sim_send_d(dut.d_input, dut.s_input, 0, BIT_TIME)
        yield from ds_sim_send_d(dut.d_input, dut.s_input, 0, BIT_TIME)

    def ds_input():
        yield dut.s_input.eq(0)
        yield dut.d_input.eq(0)
        yield Delay(SIMSTART)
        yield from ds_sim_send_null(dut.d_input, dut.s_input, BIT_TIME)
        yield from ds_sim_send_null(dut.d_input, dut.s_input, BIT_TIME)
        yield from ds_send_simultaneous()
        yield from ds_sim_send_null(dut.d_input, dut.s_input, BIT_TIME)
        yield from ds_sim_send_null(dut.d_input, dut.s_input, BIT_TIME)
        yield from ds_sim_send_null(dut.d_input, dut.s_input, BIT_TIME)
        yield from ds_send_simultaneous()
        yield from ds_sim_send_null(dut.d_input, dut.s_input, BIT_TIME)
        yield from ds_sim_send_null(dut.d_input, dut.s_input, BIT_TIME)
        yield from ds_sim_send_null(dut.d_input, dut.s_input, BIT_TIME)
        for _ in range(10):
            yield from ds_sim_send_null(dut.d_input, dut.s_input, BIT_TIME)

    def test_nulls():
        yield Delay(SIMSTART)
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME, dut.o_debug_rx_got_null, 2)

    def test_null_after_simultaneous():
        yield Delay(SIMSTART)
        yield Delay(CHAR_TIME * 10)
        while (yield dut.link_state != SpWNodeFSMStates.ERROR_WAIT):
            yield Delay(CHAR_TIME * 2)
        # Give a chance to sync with first ESC
        yield Delay(CHAR_TIME * 2)
        yield from validate_symbol_received(SRCFREQ, BIT_TIME, dut.o_debug_rx_got_null)

    sim.add_process(init)
    sim.add_process(ds_input)
    sim.add_sync_process(test_nulls)
    sim.add_sync_process(test_null_after_simultaneous)

    with sim.write_vcd(get_vcd_filename(), get_gtkw_filename(), traces=dut.ports()):
        sim.run()

tests = [test_6_3_2_a]