# amaranth: UnusedElaboratable=no
import unittest

from amaranth import *
from amaranth.sim import Simulator, Delay, Settle

from amaranth_spacewire import SpWNode, SpWTransmitterStates, SpWNodeFSMStates
from amaranth_spacewire.spw_test_utils import *

SRCFREQ = 30e6
SIMSTART = 10e-6
TX_FREQ = 10e6
BIT_TIME = 1/TX_FREQ
CHAR_TIME = BIT_TIME * 4

class test73e(unittest.TestCase):
    def setUp(self):

        m = Module()
        m.submodules.dut = self.dut = SpWNode(srcfreq=SRCFREQ, txfreq=TX_FREQ, debug=True, time_master=True)
        m.d.comb += [
            self.dut.link_disabled.eq(0),
            self.dut.link_start.eq(1),
            self.dut.autostart.eq(1),
            self.dut.r_en.eq(0),
            self.dut.soft_reset.eq(0),
            self.dut.w_en.eq(0)
        ]

        self.sim = Simulator(m)
        self.sim.add_clock(1/SRCFREQ)
        self.sim.add_clock(1/TX_FREQ, domain=ClockDomain("tx"))

    def ds_input(self):
        sent_fct = False
        while (yield self.dut.link_state != SpWNodeFSMStates.ERROR_WAIT):
            yield Tick()
        for _ in range(20):
            if not sent_fct and (yield self.dut.link_state == SpWNodeFSMStates.CONNECTING):
                yield from ds_sim_send_fct(self.dut.d_input, self.dut.s_input, BIT_TIME)
                break
            else:
                yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, BIT_TIME);

        yield from ds_sim_send_esc(self.dut.d_input, self.dut.s_input, BIT_TIME)
        yield from ds_sim_send_esc(self.dut.d_input, self.dut.s_input, BIT_TIME)

    def _test_nulls(self):
        yield Delay(SIMSTART)
        while (yield self.dut.link_state != SpWNodeFSMStates.RUN):
            yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME, self.dut.o_debug_rx_got_null, 1)

    def _test_escape_error_1(self):
        yield Delay(SIMSTART)
        while (yield self.dut.link_state != SpWNodeFSMStates.CONNECTING):
            yield Tick()
        yield from validate_symbol_received(SRCFREQ, BIT_TIME, self.dut.link_error)

    def test_spec_7_3_e_esc_esc(self):
        self.sim.add_process(self.ds_input)
        self.sim.add_process(self._test_nulls)
        self.sim.add_sync_process(self._test_escape_error_1)

        vcd = get_vcd_filename()
        gtkw = get_gtkw_filename()
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.dut.ports()):
            self.sim.run()
