import unittest

from amaranth import *
from amaranth.sim import Simulator, Delay, Settle
from amaranth_spacewire import SpWNode, SpWNodeFSMStates, SpWTransmitter, SpWReceiver
from amaranth_spacewire.spw_test_utils import *

SRCFREQ = 20e6
BIT_TIME_TX_RESET = 1 / SpWTransmitter.TX_FREQ_RESET
CHAR_TIME_TX_RESET = 4 * BIT_TIME_TX_RESET
BIT_FREQ_TX_USER = 4e6
BIT_TIME_TX_USER = ds_round_bit_time(BIT_FREQ_TX_USER, SRCFREQ)
CHAR_TIME_TX_USER = 4 * BIT_TIME_TX_USER

class test665ab(unittest.TestCase):
    def setUp(self):
        self.node = SpWNode(srcfreq=SRCFREQ, txfreq=BIT_FREQ_TX_USER, debug=True)
        self.rx = SpWReceiver(srcfreq=SRCFREQ)
        m = Module()
        m.submodules.node = self.node
        m.submodules.rx = self.rx

        self.i_switch_to_user_tx_freq = Signal()

        m.d.comb += [
            self.node.switch_to_user_tx_freq.eq(self.i_switch_to_user_tx_freq),
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

    def send_nulls(self):
        sent_fct = False
        while (yield self.node.link_state != SpWNodeFSMStates.ERROR_WAIT):
            yield
        for _ in range(100):
            if not sent_fct and (yield self.node.link_state == SpWNodeFSMStates.CONNECTING):
                yield from ds_sim_send_fct(self.node.d_input, self.node.s_input, SRCFREQ, BIT_TIME_TX_RESET)
                sent_fct = True
            else:
                yield from ds_sim_send_null(self.node.d_input, self.node.s_input, SRCFREQ, BIT_TIME_TX_RESET)

    def _test_null_detected_in_rx(self):
        while not (yield self.node.s_output):
            yield
        yield from ds_sim_delay(2 * CHAR_TIME_TX_RESET, SRCFREQ)
        waited = yield from validate_symbol_received(SRCFREQ, BIT_TIME_TX_RESET, self.rx.o_got_null)
        yield from ds_sim_delay(7 * CHAR_TIME_TX_RESET - waited, SRCFREQ)
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME_TX_RESET, self.rx.o_got_null, 3)

    def wait_before_change_freq_to_user(self):
        while not (yield self.node.s_output):
            yield
        while (yield self.node.link_state != SpWNodeFSMStates.RUN):
            yield from ds_sim_delay(CHAR_TIME_TX_RESET, SRCFREQ)
        for _ in range(15):
            yield from ds_sim_delay(CHAR_TIME_TX_RESET, SRCFREQ)

    def wait_user_freq_started(self):
        while not (yield self.node.debug_tr.o_debug_mux_sel):
            yield
        # Wait for clock off
        for _ in range(3):
            yield from ds_sim_delay(BIT_TIME_TX_RESET, SRCFREQ)
        while (yield self.node.debug_tr.o_debug_mux_clk):
            yield
        while not (yield self.node.debug_tr.o_debug_mux_clk):
            yield

    def wait_user_freq_active(self):
        yield from ds_sim_delay(15 * 2 * CHAR_TIME_TX_USER, SRCFREQ)

    def wait_user_freq_stopped(self):
        while (yield self.node.debug_tr.o_debug_mux_sel):
            yield
        # Wait for clock off
        for _ in range(3):
            yield from ds_sim_delay(BIT_TIME_TX_USER, SRCFREQ)
        while (yield self.node.debug_tr.o_debug_mux_clk):
            yield
        while not (yield self.node.debug_tr.o_debug_mux_clk):
            yield

    def wait_reset_freq_active(self):
        yield from ds_sim_delay(15 * 2 * CHAR_TIME_TX_USER, SRCFREQ)

    def change_tx_freq(self):
        yield from self.wait_before_change_freq_to_user()
        yield self.i_switch_to_user_tx_freq.eq(1)
        yield from self.wait_user_freq_started()
        yield from self.wait_user_freq_active()
        yield self.i_switch_to_user_tx_freq.eq(0)
        yield from self.wait_user_freq_stopped()
        yield from self.wait_reset_freq_active()

    def _test_null_detected_in_rx_user_freq_after_reset_freq(self):
        yield from self.wait_before_change_freq_to_user()
        yield from self.wait_user_freq_started()
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME_TX_USER, self.rx.o_got_null, 14)

    def _test_null_detected_in_rx_reset_freq_after_user_freq(self):
        yield from self.wait_before_change_freq_to_user()
        yield from self.wait_user_freq_started()
        yield from self.wait_user_freq_active()
        yield from self.wait_user_freq_stopped()
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME_TX_RESET, self.rx.o_got_null, 14)

    def test_spec_6_6_5_a_b(self):
        self.sim.add_sync_process(self.send_nulls)
        self.sim.add_sync_process(self.change_tx_freq)
        self.sim.add_sync_process(self._test_null_detected_in_rx)
        self.sim.add_sync_process(self._test_null_detected_in_rx_user_freq_after_reset_freq)
        self.sim.add_sync_process(self._test_null_detected_in_rx_reset_freq_after_user_freq)

        vcd = get_vcd_filename()
        gtkw = get_gtkw_filename()
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.node.ports()):
            self.sim.run()
