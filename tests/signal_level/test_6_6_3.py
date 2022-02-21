import unittest

from amaranth import *
from amaranth.sim import Simulator, Delay

from amaranth_spacewire import SpWNode, SpWNodeFSMStates, SpWReceiver
from amaranth_spacewire.spw_test_utils import *

SRCFREQ = 35e6
BIT_FREQ_RX = 5e6
BIT_TIME_RX = 1 / BIT_FREQ_RX
CHAR_TIME_RX = 4 * BIT_TIME_RX
# Use reset frequency to avoid managing two frequencies
BIT_FREQ_TX = 10e6
BIT_TIME_TX = ds_round_bit_time(BIT_FREQ_TX, SRCFREQ)
CHAR_TIME_TX = 4 * BIT_TIME_TX

class test663(unittest.TestCase):
    def setUp(self):
        self.node = SpWNode(srcfreq=SRCFREQ, txfreq=BIT_FREQ_TX, debug=True)
        self.rx = SpWReceiver(srcfreq=SRCFREQ)
        m = Module()
        m.submodules.node = self.node
        m.submodules.rx = self.rx

        m.d.comb += [
            self.node.link_disabled.eq(0),
            self.node.link_start.eq(1),
            self.node.autostart.eq(1),
            self.node.r_en.eq(0),
            self.node.soft_reset.eq(0),
            self.node.tick_input.eq(0),
            self.node.w_en.eq(0),

            self.rx.i_reset.eq(0),
            self.rx.i_d.eq(self.node.d_output),
            self.rx.i_s.eq(self.node.s_output)
        ]

        self.sim = Simulator(m)
        self.sim.add_clock(1/SRCFREQ)

        assert(BIT_FREQ_RX != BIT_FREQ_TX)

    def send_nulls(self):
        sent_fct = False
        while (yield self.node.link_state != SpWNodeFSMStates.ERROR_WAIT):
            yield Tick()
        for _ in range(50):
            if not sent_fct and (yield self.node.link_state == SpWNodeFSMStates.CONNECTING):
                yield from ds_sim_send_fct(self.node.d_input, self.node.s_input, SRCFREQ, BIT_TIME_RX)
                sent_fct = True
            else:
                yield from ds_sim_send_null(self.node.d_input, self.node.s_input, SRCFREQ, BIT_TIME_RX)

    def _test_null_detected_in_node(self):
        while not (yield self.node.s_input):
            yield Tick()
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME_RX, self.node.o_debug_rx_got_null, 3)

    # As we are sending NULLs from the beginning, there will be 1 NULL then 7 FCTs then NULLs
    def _test_null_detected_in_rx(self):
        while not (yield self.node.s_output):
            yield Tick()
        waited = yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME_TX, self.rx.o_got_null, 1)
        yield from ds_sim_delay(7 * CHAR_TIME_TX - waited, SRCFREQ)
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME_TX, self.rx.o_got_null, 10)

    def test_spec_6_6_3(self):
        self.sim.add_process(self.send_nulls)
        self.sim.add_process(self._test_null_detected_in_node)
        self.sim.add_process(self._test_null_detected_in_rx)

        vcd = get_vcd_filename()
        gtkw = get_gtkw_filename()
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.node.ports()):
            self.sim.run()
