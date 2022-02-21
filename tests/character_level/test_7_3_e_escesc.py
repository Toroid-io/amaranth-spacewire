# amaranth: UnusedElaboratable=no
import unittest

from amaranth import *
from amaranth.sim import Simulator, Delay, Settle

from amaranth_spacewire import SpWNode, SpWTransmitterStates, SpWNodeFSMStates
from amaranth_spacewire.spw_test_utils import *

SRCFREQ = 30e6
SIMSTART = 10e-6
TX_FREQ = 10e6
BIT_TIME = ds_round_bit_time(TX_FREQ, SRCFREQ)
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

    def ds_nulls(self):
        sent_fct = False
        while (yield self.dut.link_state != SpWNodeFSMStates.ERROR_WAIT):
            yield Tick()
        for _ in range(20):
            if not sent_fct and (yield self.dut.link_state == SpWNodeFSMStates.CONNECTING):
                yield from ds_sim_send_fct(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
                sent_fct = True
            else:
                yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME);

    def ds_input(self):
        yield from self.ds_nulls()
        yield from ds_sim_send_esc(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_esc(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)

        yield from self.ds_nulls()
        yield from ds_sim_send_esc(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_eop(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)

        yield from self.ds_nulls()
        yield from ds_sim_send_esc(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_eep(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)

        yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)

    def _test_nulls(self):
        while (yield self.dut.link_state != SpWNodeFSMStates.ERROR_WAIT):
            yield Tick()
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME, self.dut.o_debug_rx_got_null, 1)

    def reset_link(self):
        yield self.dut.link_error_clear.eq(1)
        yield Tick()
        yield self.dut.link_error_clear.eq(0)
        yield Tick()

    def inter_error_delay(self):
        # Nulls ...
        for _ in range(19):
            yield from ds_sim_delay(2 * CHAR_TIME, SRCFREQ)
        # And one FCT
        yield from ds_sim_delay(CHAR_TIME, SRCFREQ)

    def _test_escape_error(self):
        while (yield self.dut.link_state != SpWNodeFSMStates.ERROR_WAIT):
            yield Tick()
        yield from self.inter_error_delay()
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME, self.dut.link_error, 1)
        yield from self.reset_link()

        while (yield self.dut.link_state != SpWNodeFSMStates.ERROR_WAIT):
            yield Tick()
        yield from self.inter_error_delay()
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME, self.dut.link_error, 1)
        yield from self.reset_link()

        while (yield self.dut.link_state != SpWNodeFSMStates.ERROR_WAIT):
            yield Tick()
        yield from self.inter_error_delay()
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME, self.dut.link_error, 1)
        yield from self.reset_link()

    def test_spec_7_3_e(self):
        self.sim.add_process(self.ds_input)
        self.sim.add_process(self._test_nulls)
        self.sim.add_process(self._test_escape_error)

        vcd = get_vcd_filename()
        gtkw = get_gtkw_filename()
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.dut.ports()):
            self.sim.run()
