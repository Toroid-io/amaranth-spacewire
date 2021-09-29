from nmigen import *
from nmigen.sim import Simulator, Delay, Settle
from spw_node.src.spw_node import SpWNode, SpWNodeFSMStates, SpWTransmitter
from spw_node.src.spw_receiver import SpWReceiver
from spw_node.test.spw_test_utils import *


def test_6_6_5_a_b():

    SRCFREQ = 20e6
    BIT_TIME_TX_RESET = 1 / SpWTransmitter.TX_FREQ_RESET
    CHAR_TIME_TX_RESET = 4 * BIT_TIME_TX_RESET
    BIT_FREQ_TX_USER = 4e6
    BIT_TIME_TX_USER = 1 / BIT_FREQ_TX_USER
    CHAR_TIME_TX_USER = 4 * BIT_TIME_TX_USER

    node = SpWNode(SRCFREQ, BIT_FREQ_TX_USER, debug=True)
    rx = SpWReceiver(SRCFREQ)
    m = Module()
    m.submodules.node = node
    m.submodules.rx = rx

    i_switch_to_user_tx_freq = Signal()

    m.d.comb += [
        node.i_switch_to_user_tx_freq.eq(i_switch_to_user_tx_freq),
        node.i_link_disabled.eq(0),
        node.i_link_start.eq(1),
        node.i_autostart.eq(1),
        node.i_r_en.eq(0),
        node.i_reset.eq(0),
        node.i_tick.eq(0),
        node.i_w_en.eq(0),

        rx.i_reset.eq(0),
        rx.i_d.eq(node.o_d),
        rx.i_s.eq(node.o_s)
    ]

    sim = Simulator(m)
    sim.add_clock(1/SRCFREQ)

    def send_nulls():
        sent_fct = False
        while (yield node.o_debug_fsm_state != SpWNodeFSMStates.ERROR_WAIT):
            yield
        for _ in range(100):
            if not sent_fct and (yield node.o_debug_fsm_state == SpWNodeFSMStates.CONNECTING):
                yield from ds_sim_send_fct(node.i_d, node.i_s, BIT_TIME_TX_RESET)
                sent_fct = True
            else:
                yield from ds_sim_send_null(node.i_d, node.i_s, BIT_TIME_TX_RESET)

    def test_null_detected_in_rx():
        while not (yield node.o_s):
            yield
        yield Delay(7 * CHAR_TIME_TX_RESET)
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME_TX_RESET, rx.o_got_null, 3)

    def wait_before_change_freq_to_user():
        while not (yield node.o_s):
            yield
        while (yield node.o_debug_fsm_state != SpWNodeFSMStates.RUN):
            yield Delay(CHAR_TIME_TX_RESET)
        for _ in range(10):
            yield Delay(CHAR_TIME_TX_RESET)

    def wait_user_freq_started():
        while not (yield node.debug_tr.o_debug_mux_sel):
            yield
        # Wait for clock off
        for _ in range(3):
            yield Delay(BIT_TIME_TX_RESET)
        while (yield node.debug_tr.o_debug_mux_clk):
            yield
        while not (yield node.debug_tr.o_debug_mux_clk):
            yield

    def wait_user_freq_active():
        yield Delay(15 * 2 * CHAR_TIME_TX_USER)

    def wait_user_freq_stopped():
        while (yield node.debug_tr.o_debug_mux_sel):
            yield
        # Wait for clock off
        for _ in range(3):
            yield Delay(BIT_TIME_TX_USER)
        while (yield node.debug_tr.o_debug_mux_clk):
            yield
        while not (yield node.debug_tr.o_debug_mux_clk):
            yield

    def wait_reset_freq_active():
        yield Delay(15 * 2 * CHAR_TIME_TX_USER)

    def change_tx_freq():
        yield from wait_before_change_freq_to_user()
        yield i_switch_to_user_tx_freq.eq(1)
        yield from wait_user_freq_started()
        yield from wait_user_freq_active()
        yield i_switch_to_user_tx_freq.eq(0)
        yield from wait_user_freq_stopped()
        yield from wait_reset_freq_active()

    def test_null_detected_in_rx_user_freq_after_reset_freq():
        yield from wait_before_change_freq_to_user()
        yield from wait_user_freq_started()
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME_TX_USER, rx.o_got_null, 14)

    def test_null_detected_in_rx_reset_freq_after_user_freq():
        yield from wait_before_change_freq_to_user()
        yield from wait_user_freq_started()
        yield from wait_user_freq_active()
        yield from wait_user_freq_stopped()
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME_TX_RESET, rx.o_got_null, 14)

    sim.add_sync_process(send_nulls)
    sim.add_sync_process(change_tx_freq)
    sim.add_sync_process(test_null_detected_in_rx)
    sim.add_sync_process(test_null_detected_in_rx_user_freq_after_reset_freq)
    sim.add_sync_process(test_null_detected_in_rx_reset_freq_after_user_freq)

    with sim.write_vcd(get_vcd_filename(), get_gtkw_filename(), traces=node.ports()):
        sim.run()

tests = [test_6_6_5_a_b]