from amaranth import *
from amaranth.sim import Simulator, Delay, Settle
from spw_node.src.spw_node import SpWNode, SpWNodeFSMStates, SpWTransmitter
from spw_node.src.spw_receiver import SpWReceiver
from spw_node.test.spw_test_utils import *


def test_6_6_6():

    SRCFREQ = 20e6
    BIT_TIME_TX_RESET = 1 / SpWTransmitter.TX_FREQ_RESET
    BIT_FREQ_TX_USER = 4e6

    node = SpWNode(SRCFREQ, BIT_FREQ_TX_USER, debug=True)
    m = Module()
    m.submodules.node = node

    i_switch_to_user_tx_freq = Signal()

    m.d.comb += [
        node.switch_to_user_tx_freq.eq(i_switch_to_user_tx_freq),
        node.link_disabled.eq(0),
        node.link_start.eq(1),
        node.autostart.eq(1),
        node.r_en.eq(0),
        node.soft_reset.eq(0),
        node.tick_input.eq(0),
        node.w_en.eq(0)
    ]

    sim = Simulator(m)
    sim.add_clock(1/SRCFREQ)

    def send_nulls():
        sent_fct = False
        while (yield node.link_state != SpWNodeFSMStates.ERROR_WAIT):
            yield
        for _ in range(100):
            if not sent_fct and (yield node.link_state == SpWNodeFSMStates.CONNECTING):
                yield from ds_sim_send_fct(node.d_input, node.s_input, BIT_TIME_TX_RESET)
                sent_fct = True
            else:
                yield from ds_sim_send_null(node.d_input, node.s_input, BIT_TIME_TX_RESET)
        yield from ds_sim_send_wrong_null(node.d_input, node.s_input, BIT_TIME_TX_RESET)
        for _ in range(50):
            yield from ds_sim_send_null(node.d_input, node.s_input, BIT_TIME_TX_RESET)

    def test():
        yield i_switch_to_user_tx_freq.eq(1)
        while ((yield node.link_state != SpWNodeFSMStates.RUN) and not (yield node.debug_tr.o_ready)):
            yield
            yield Settle()
            assert(yield node.debug_tr.i_switch_to_user_tx_freq == 0)
        while (yield node.link_state == SpWNodeFSMStates.RUN):
            yield Settle()
            assert(yield node.debug_tr.i_switch_to_user_tx_freq == 1)
        yield
        yield Settle()
        assert(yield node.debug_tr.i_switch_to_user_tx_freq == 0)

    sim.add_sync_process(send_nulls)
    sim.add_sync_process(test)

    with sim.write_vcd(get_vcd_filename(), get_gtkw_filename(), traces=node.ports()):
        sim.run()

tests = [test_6_6_6]