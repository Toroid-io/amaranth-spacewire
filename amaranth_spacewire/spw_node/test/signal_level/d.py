from amaranth import *
from amaranth.sim import Simulator, Delay
from spw_node.src.spw_node import SpWNode, SpWNodeFSMStates
from spw_node.src.spw_receiver import SpWReceiver
from spw_node.test.spw_test_utils import *


def test_6_6_3():

    SRCFREQ = 20e6
    BIT_FREQ_RX = 5e6
    BIT_TIME_RX = 1 / BIT_FREQ_RX
    CHAR_TIME_RX = 4 * BIT_TIME_RX
    # Use reset frequency to avoid managing two frequencies
    BIT_FREQ_TX = 10e6
    BIT_TIME_TX = 1 / BIT_FREQ_TX
    CHAR_TIME_TX = 4 * BIT_TIME_TX

    node = SpWNode(SRCFREQ, BIT_FREQ_TX, debug=True)
    rx = SpWReceiver(SRCFREQ)
    m = Module()
    m.submodules.node = node
    m.submodules.rx = rx

    m.d.comb += [
        node.link_disabled.eq(0),
        node.link_start.eq(1),
        node.autostart.eq(1),
        node.r_en.eq(0),
        node.soft_reset.eq(0),
        node.tick_input.eq(0),
        node.w_en.eq(0),

        rx.i_reset.eq(0),
        rx.i_d.eq(node.d_output),
        rx.i_s.eq(node.s_output)
    ]

    sim = Simulator(m)
    sim.add_clock(1/SRCFREQ)

    assert(BIT_FREQ_RX != BIT_FREQ_TX)

    def send_nulls():
        sent_fct = False
        while (yield node.link_state != SpWNodeFSMStates.ERROR_WAIT):
            yield
        for _ in range(50):
            if not sent_fct and (yield node.link_state == SpWNodeFSMStates.CONNECTING):
                yield from ds_sim_send_fct(node.d_input, node.s_input, 1/BIT_FREQ_RX)
                sent_fct = True
            else:
                yield from ds_sim_send_null(node.d_input, node.s_input, 1/BIT_FREQ_RX)

    def test_null_detected_in_node():
        while (yield node.link_state != SpWNodeFSMStates.ERROR_WAIT):
            yield
        while not (yield node.s_input):
            yield
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME_RX, node.o_debug_rx_got_null, 3)

    # As we are sending NULLs from the beginning, there will be 1 NULL then 7 FCTs then NULLs
    def test_null_detected_in_rx():
        while not (yield node.s_output):
            yield
        yield Delay(2 * CHAR_TIME_TX)
        waited = yield from validate_symbol_received(SRCFREQ, BIT_TIME_TX, rx.o_got_null)
        yield Delay(7 * CHAR_TIME_TX - waited)
        yield from validate_multiple_symbol_received(SRCFREQ, BIT_TIME_TX, rx.o_got_null, 10)

    sim.add_sync_process(send_nulls)
    sim.add_sync_process(test_null_detected_in_node)
    sim.add_sync_process(test_null_detected_in_rx)

    with sim.write_vcd(get_vcd_filename(), get_gtkw_filename(), traces=node.ports()):
        sim.run()

tests = [test_6_6_3]