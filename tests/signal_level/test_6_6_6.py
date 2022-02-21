import unittest

from amaranth import *
from amaranth.sim import Simulator, Settle

from amaranth_spacewire import SpWNode, SpWNodeFSMStates, SpWTransmitter, SpWReceiver
from amaranth_spacewire.spw_test_utils import *

SRCFREQ = 20e6
BIT_TIME_TX_RESET = 1 / SpWTransmitter.TX_FREQ_RESET
BIT_FREQ_TX_USER = 4e6

class test_6_6_6(unittest.TestCase):
    def setUp(self):
        self.node = SpWNode(srcfreq=SRCFREQ, txfreq=BIT_FREQ_TX_USER, debug=True)
        m = Module()
        m.submodules.node = self.node

        self.i_switch_to_user_tx_freq = Signal()

        m.d.comb += [
            self.node.switch_to_user_tx_freq.eq(self.i_switch_to_user_tx_freq),
            self.node.link_disabled.eq(0),
            self.node.link_start.eq(1),
            self.node.autostart.eq(1),
            self.node.r_en.eq(0),
            self.node.soft_reset.eq(0),
            self.node.tick_input.eq(0),
            self.node.w_en.eq(0)
        ]

        self.sim = Simulator(m)
        self.sim.add_clock(1/SRCFREQ)

    def send_nulls(self):
        sent_fct = False
        while (yield self.node.link_state != SpWNodeFSMStates.ERROR_WAIT):
            yield Tick()
        for _ in range(100):
            if not sent_fct and (yield self.node.link_state == SpWNodeFSMStates.CONNECTING):
                yield from ds_sim_send_fct(self.node.d_input, self.node.s_input, SRCFREQ, BIT_TIME_TX_RESET)
                sent_fct = True
            else:
                yield from ds_sim_send_null(self.node.d_input, self.node.s_input, SRCFREQ, BIT_TIME_TX_RESET)
        yield from ds_sim_send_wrong_null(self.node.d_input, self.node.s_input, SRCFREQ, BIT_TIME_TX_RESET)
        for _ in range(50):
            yield from ds_sim_send_null(self.node.d_input, self.node.s_input, SRCFREQ, BIT_TIME_TX_RESET)

    def _test(self):
        yield self.i_switch_to_user_tx_freq.eq(1)
        yield Tick()
        while ((yield self.node.link_state != SpWNodeFSMStates.RUN) and not (yield self.node.debug_tr.o_ready)):
            yield Tick()
            yield Settle()
            assert(yield self.node.debug_tr.i_switch_to_user_tx_freq == 0)
        while (yield self.node.link_state == SpWNodeFSMStates.RUN):
            yield Tick()
            yield Settle()
            assert(yield self.node.debug_tr.i_switch_to_user_tx_freq == 1)
        yield Tick()
        yield Settle()
        assert(yield self.node.debug_tr.i_switch_to_user_tx_freq == 0)

    def test_spec_6_6_6(self):
        self.sim.add_process(self.send_nulls)
        self.sim.add_process(self._test)

        vcd = get_vcd_filename()
        gtkw = get_gtkw_filename()
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.node.ports()):
            self.sim.run()
