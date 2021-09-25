from nmigen import *
from nmigen.sim import Simulator, Delay, Settle
from spw_node.src.spw_node import SpWNode, SpWNodeFSMStates
from spw_node.test.spw_test_utils import *

def test_6_3_2_a():

    SRCFREQ = 10e6
    SIMSTART = 20e-6
    BIT_TIME = 0.5e-6
    CHAR_TIME = BIT_TIME * 4

    dut = SpWNode(srcfreq=SRCFREQ, txfreq=1/BIT_TIME, disconnect_delay=1, debug=True)

    sim = Simulator(dut)
    sim.add_clock(1/SRCFREQ)

    def init():
        yield dut.i_link_disabled.eq(0)
        yield dut.i_link_start.eq(1)
        yield dut.i_autostart.eq(1)
        yield dut.i_r_en.eq(0)
        yield dut.i_reset.eq(0)
        yield dut.i_tick.eq(0)
        yield dut.i_w_en.eq(0)
        yield Settle()

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

    def test_first_null():
        yield Delay(SIMSTART)
        yield Delay(CHAR_TIME * 2)
        yield from validate_symbol_received(BIT_TIME, dut.o_debug_rx_got_null)

    def test_second_null():
        yield Delay(SIMSTART)
        yield Delay(CHAR_TIME * 4)
        yield from validate_symbol_received(BIT_TIME, dut.o_debug_rx_got_null)

    def test_null_after_simultaneous():
        yield Delay(SIMSTART)
        yield Delay(CHAR_TIME * 10)
        while (yield dut.o_debug_fsm_state != SpWNodeFSMStates.ERROR_WAIT):
            yield Delay(CHAR_TIME * 2)
        # Give a chance to sync with first ESC
        yield Delay(CHAR_TIME * 2)
        yield from validate_symbol_received(BIT_TIME, dut.o_debug_rx_got_null)

    sim.add_process(init)
    sim.add_process(ds_input)
    sim.add_sync_process(test_null_after_simultaneous)

    with sim.write_vcd(get_vcd_filename(), get_gtkw_filename(), traces=dut.ports()):
        sim.run_until(50e-6)

tests = [test_6_3_2_a]