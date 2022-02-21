import unittest

from amaranth import *
from amaranth.sim import Simulator, Delay, Settle
from amaranth_spacewire import SpWNode, SpWNodeFSMStates
from amaranth_spacewire.spw_test_utils import *

SRCFREQ = 22e6
SIMSTART = 20e-6
# Use reset frequency to avoid managing two frequencies
TX_FREQ = 10e6
BIT_TIME = ds_round_bit_time(TX_FREQ, SRCFREQ)
CHAR_TIME = BIT_TIME * 4

class test632a(unittest.TestCase):
    def setUp(self):
        self.dut = SpWNode(srcfreq=SRCFREQ, txfreq=TX_FREQ, disconnect_delay=1, debug=True)

        self.sim = Simulator(self.dut)
        self.sim.add_clock(1/SRCFREQ)

    def init(self):
        yield self.dut.link_disabled.eq(0)
        yield self.dut.link_start.eq(1)
        yield self.dut.autostart.eq(1)
        yield self.dut.r_en.eq(0)
        yield self.dut.soft_reset.eq(0)
        yield self.dut.tick_input.eq(0)
        yield self.dut.w_en.eq(0)
        yield Settle()

    def ds_send_simultaneous(self):
        yield from ds_sim_send_d(self.dut.d_input, self.dut.s_input, 0, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_d(self.dut.d_input, self.dut.s_input, 1, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_d(self.dut.d_input, self.dut.s_input, 1, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_d(self.dut.d_input, self.dut.s_input, 1, SRCFREQ, BIT_TIME)
        yield self.dut.d_input.eq(0)
        yield self.dut.s_input.eq(0)
        yield from ds_sim_delay(BIT_TIME, SRCFREQ)
        yield from ds_sim_send_d(self.dut.d_input, self.dut.s_input, 1, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_d(self.dut.d_input, self.dut.s_input, 0, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_d(self.dut.d_input, self.dut.s_input, 0, SRCFREQ, BIT_TIME)

    def ds_input(self):
        yield self.dut.s_input.eq(0)
        yield self.dut.d_input.eq(0)
        yield from ds_sim_delay(SIMSTART, SRCFREQ)
        yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from self.ds_send_simultaneous()
        yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from self.ds_send_simultaneous()
        yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        for _ in range(10):
            yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)

    def _test_nulls(self):
        yield from ds_sim_delay(SIMSTART, SRCFREQ)
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME, self.dut.o_debug_rx_got_null, 2)

    def _test_null_after_simultaneous(self):
        yield from ds_sim_delay(SIMSTART, SRCFREQ)
        yield from ds_sim_delay(CHAR_TIME * 10, SRCFREQ)
        while (yield self.dut.link_state != SpWNodeFSMStates.ERROR_WAIT):
            yield from ds_sim_delay(CHAR_TIME * 2, SRCFREQ)
        # Give a chance to sync with first ESC
        yield from ds_sim_delay(CHAR_TIME * 2, SRCFREQ)
        yield from validate_symbol_received(SRCFREQ, BIT_TIME, self.dut.o_debug_rx_got_null)

    def test_spec_6_3_2_a(self):
        self.sim.add_process(self.init)
        self.sim.add_process(self.ds_input)
        self.sim.add_process(self._test_nulls)
        self.sim.add_process(self._test_null_after_simultaneous)

        vcd = get_vcd_filename()
        gtkw = get_gtkw_filename()
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.dut.ports()):
            self.sim.run()
