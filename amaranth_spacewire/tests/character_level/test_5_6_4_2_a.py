# amaranth: UnusedElaboratable=no
import unittest

from amaranth import *
from amaranth.sim import Simulator

from amaranth_spacewire import SpWNode, SpWTransmitterStates, SpWNodeFSMStates
from amaranth_spacewire.tests.spw_test_utils import *

SRCFREQ = 30e6
SIMSTART = 20e-6
TX_FREQ = 10e6
BIT_TIME = 1/TX_FREQ
CHAR_TIME = BIT_TIME * 4

class Test(unittest.TestCase):
    def setUp(self):

        m = Module()
        m.submodules.dut = self.dut = SpWNode(srcfreq=SRCFREQ, rstfreq=TX_FREQ, txfreq=TX_FREQ, disconnect_delay=1, debug=True, time_master=True)
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

    def send_nulls(self):
        yield from ds_sim_delay(SIMSTART, SRCFREQ)
        for _ in range(5):
            yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_fct(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        for _ in range(100):
            yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)

    def ticks(self):
        yield from ds_sim_delay(SIMSTART, SRCFREQ)
        while (yield self.dut.link_state != SpWNodeFSMStates.RUN):
            yield Tick()
        for _ in range(50):
            for _ in range(ds_sim_period_to_ticks(10e-6, SRCFREQ)):
                yield Tick()
            yield self.dut.tick_input.eq(1)
            yield Tick()
            yield self.dut.tick_input.eq(0)

    def _test_time_codes(self):
        time_counter = 0
        yield from ds_sim_delay(SIMSTART, SRCFREQ)
        for _ in range(50):
            while (yield self.dut.o_debug_tr_send_time == 0):
                yield Tick()
            time_counter = yield self.dut.o_debug_time_counter
            while (yield self.dut.o_debug_tr_send_time == 1):
                yield Tick()
            while (yield self.dut.o_debug_tr_fsm_state != SpWTransmitterStates.SEND_TIME_C):
                yield Tick()
            assert((yield self.dut.o_debug_tr_sr_input[:6]) == time_counter)

    def test_spec_5_6_4_2_a(self):
        self.sim.add_process(self.send_nulls)
        self.sim.add_process(self.ticks)
        self.sim.add_process(self._test_time_codes)

        vcd = get_vcd_filename()
        gtkw = get_gtkw_filename()
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.dut.ports()):
            self.sim.run()


if __name__ == "__main__":
    unittest.main()