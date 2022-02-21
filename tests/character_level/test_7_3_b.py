import unittest

from amaranth import *
from amaranth.sim import Simulator, Settle

from amaranth_spacewire import SpWNode, SpWTransmitterStates
from amaranth_spacewire.spw_test_utils import *

SRCFREQ = 20e6
SIMSTART = 20e-6
TX_FREQ = 10e6
BIT_TIME = 1/TX_FREQ
CHAR_TIME = BIT_TIME * 4

class test73b(unittest.TestCase):
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
        yield Tick()

    def send_nulls(self):
        yield from ds_sim_delay(SIMSTART, SRCFREQ)
        for _ in range(5):
            yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        yield from ds_sim_send_fct(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)
        for _ in range(50):
            yield from ds_sim_send_null(self.dut.d_input, self.dut.s_input, SRCFREQ, BIT_TIME)

    def monitor_send_null(self):
        yield from ds_sim_delay(SIMSTART, SRCFREQ)
        for _ in range(ds_sim_period_to_ticks(200e-6, SRCFREQ)):
            if ( (yield self.dut.debug_tr.o_debug_fsm_state == SpWTransmitterStates.WAIT) &
                 (yield self.dut.debug_tr.o_ready) &
                 ~ (yield self.dut.debug_tr.i_send_char) &
                 ~ (yield self.dut.debug_tr.i_send_eep) &
                 ~ (yield self.dut.debug_tr.i_send_eop) &
                 ~ (yield self.dut.debug_tr.i_send_esc) &
                 ~ (yield self.dut.debug_tr.i_send_fct) &
                 ~ (yield self.dut.debug_tr.i_send_time)):
                while(yield self.dut.debug_tr.o_debug_fsm_state == SpWTransmitterStates.WAIT):
                    yield Tick()
                assert(yield self.dut.o_debug_tr_fsm_state == SpWTransmitterStates.SEND_NULL_A)
            else:
                yield Tick()

    def test_spec_7_3_b(self):
        self.sim.add_process(self.init)
        self.sim.add_process(self.send_nulls)
        self.sim.add_process(self.monitor_send_null)

        vcd = get_vcd_filename()
        gtkw = get_gtkw_filename()
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.dut.ports()):
            self.sim.run()
