import unittest

from amaranth import *
from amaranth.sim import Simulator, Delay, Settle

from amaranth_spacewire import SpWNode, SpWNodeFSMStates
from amaranth_spacewire.spw_test_utils import *

SRCFREQ = 54e6
SIMSTART = 10e-6
TX_FREQ = 20e6
RST_FREQ = 10e6
BIT_TIME = ds_round_bit_time(TX_FREQ, SRCFREQ)
CHAR_TIME = BIT_TIME * 4

class Gate(Elaboratable):
    def __init__(self, i, o, trigger):
        self.o = o
        self.i = i
        self.trigger = trigger

    def elaborate(self, platform):
        m = Module()

        with m.If(self.trigger):
            m.d.comb += self.o.eq(self.i)
        with m.Else():
            m.d.comb += self.o.eq(0)

        return m

class SpwNode_Bench(unittest.TestCase):
    def setUp(self):
        #######################################################
        # END A
        #######################################################
        # Time functions
        self.endA_tick_input = Signal()
        self.endA_tick_output = Signal()
        self.endA_time_flags = Signal(2)
        self.endA_time_value = Signal(6)

        # FIFO
        self.endA_r_en = Signal()
        self.endA_r_data = Signal(8)
        self.endA_r_rdy = Signal()
        self.endA_w_en = Signal()
        self.endA_w_data = Signal(8)
        self.endA_w_rdy = Signal()

        # Status signals
        self.endA_link_state = Signal(SpWNodeFSMStates)
        self.endA_link_error_flags = Signal(4)

        # Control signals
        self.endA_soft_reset = Signal()
        self.endA_switch_to_user_tx_freq = Signal()
        self.endA_link_disabled = Signal()
        self.endA_link_start = Signal()
        self.endA_autostart = Signal()
        self.endA_link_error_clear = Signal()
        #######################################################

        #######################################################
        # END B
        #######################################################
        # Time functions
        self.endB_tick_input = Signal()
        self.endB_tick_output = Signal()
        self.endB_time_flags = Signal(2)
        self.endB_time_value = Signal(6)

        # FIFO
        self.endB_r_en = Signal()
        self.endB_r_data = Signal(8)
        self.endB_r_rdy = Signal()
        self.endB_w_en = Signal()
        self.endB_w_data = Signal(8)
        self.endB_w_rdy = Signal()

        # Status signals
        self.endB_link_state = Signal(SpWNodeFSMStates)
        self.endB_link_error_flags = Signal(4)

        # Control signals
        self.endB_soft_reset = Signal()
        self.endB_switch_to_user_tx_freq = Signal()
        self.endB_link_disabled = Signal()
        self.endB_link_start = Signal()
        self.endB_autostart = Signal()
        self.endB_link_error_clear = Signal()
        #######################################################

        m = Module()

        m.submodules.endA = self.endA = SpWNode(srcfreq=SRCFREQ, rstfreq=RST_FREQ, txfreq=TX_FREQ, debug=True, time_master=True)
        m.submodules.endB = self.endB = SpWNode(srcfreq=SRCFREQ, rstfreq=RST_FREQ, txfreq=TX_FREQ, debug=True, time_master=False)

        self.gate_trigger = Signal()
        m.submodules.gate = self.gate = Gate(self.endA.d_output, self.endB.d_input, self.gate_trigger)

        m.d.comb += [
            #######################################################
            # END A
            #######################################################
            # Time functions
            self.endA.d_input.eq(self.endB.d_output),
            self.endA.s_input.eq(self.endB.s_output),

            # Time functions
            self.endA.tick_input.eq(self.endA_tick_input),
            self.endA_tick_output.eq(self.endA.tick_output),
            self.endA_time_flags.eq(self.endA.time_flags),
            self.endA_time_value.eq(self.endA.time_value),

            # FIFO
            # FIFO RX
            self.endA.r_en.eq(self.endA_r_en),
            self.endA_r_data.eq(self.endA.r_data),
            self.endA_r_rdy.eq(self.endA.r_rdy),
            # FIFO TX
            self.endA.w_en.eq(self.endA_w_en),
            self.endA.w_data.eq(self.endA_w_data),
            self.endA_w_rdy.eq(self.endA.w_rdy),

            # Status signals
            self.endA_link_state.eq(self.endA.link_state),
            self.endA_link_error_flags.eq(self.endA.link_error_flags),
            
            # Control signals
            self.endA.soft_reset.eq(self.endA_soft_reset),
            self.endA.switch_to_user_tx_freq.eq(self.endA_switch_to_user_tx_freq),
            self.endA.link_disabled.eq(self.endA_link_disabled),
            self.endA.link_start.eq(self.endA_link_start),
            self.endA.autostart.eq(self.endA_autostart),
            self.endA.link_error_clear.eq(self.endA_link_error_clear),
            #######################################################

            #######################################################
            # END B
            #######################################################
            # Time functions
            #self.endB.d_input.eq(self.endA.d_output),
            self.endB.s_input.eq(self.endA.s_output),

            # Time functions
            self.endB.tick_input.eq(self.endB_tick_input),
            self.endB_tick_output.eq(self.endB.tick_output),
            self.endB_time_flags.eq(self.endB.time_flags),
            self.endB_time_value.eq(self.endB.time_value),

            # FIFO
            # FIFO RX
            self.endB.r_en.eq(self.endB_r_en),
            self.endB_r_data.eq(self.endB.r_data),
            self.endB_r_rdy.eq(self.endB.r_rdy),
            # FIFO TX
            self.endB.w_en.eq(self.endB_w_en),
            self.endB.w_data.eq(self.endB_w_data),
            self.endB_w_rdy.eq(self.endB.w_rdy),

            # Status signals
            self.endB_link_state.eq(self.endB.link_state),
            self.endB_link_error_flags.eq(self.endB.link_error_flags),
            
            # Control signals
            self.endB.soft_reset.eq(self.endB_soft_reset),
            self.endB.switch_to_user_tx_freq.eq(self.endB_switch_to_user_tx_freq),
            self.endB.link_disabled.eq(self.endB_link_disabled),
            self.endB.link_start.eq(self.endB_link_start),
            self.endB.autostart.eq(self.endB_autostart),
            self.endB.link_error_clear.eq(self.endB_link_error_clear),
            #######################################################
        ]

        m.d.comb += [
            self.endA_link_start.eq(1),
            #self.endB_link_start.eq(1),
            #self.endA_autostart.eq(1),
            self.endB_autostart.eq(1),
            self.endB_switch_to_user_tx_freq.eq(1)
        ]

        self.sim = Simulator(m)
        self.sim.add_clock(1/SRCFREQ)
        self.sim.add_clock(1/TX_FREQ, domain=ClockDomain("tx"))

    def ports(self):
        return [
            self.endA.d_input, self.endA.s_input, self.endA.d_output, self.endA.s_output, self.endA.link_state,
            self.endB.d_input, self.endB.s_input, self.endB.d_output, self.endB.s_output, self.endB.link_state,
        ]

    def _run(self):
        yield self.gate_trigger.eq(1)
        for _ in range(ds_sim_period_to_ticks(150e-6, SRCFREQ)):
            yield Tick()
        yield self.gate_trigger.eq(0)
        for _ in range(ds_sim_period_to_ticks(20e-6, SRCFREQ)):
            yield Tick()
        yield self.endA_link_error_clear.eq(1)
        for _ in range(ds_sim_period_to_ticks(1e-6, SRCFREQ)):
            yield Tick()
        yield self.endA_link_error_clear.eq(0)
        yield self.endB_link_error_clear.eq(1)
        for _ in range(ds_sim_period_to_ticks(1e-6, SRCFREQ)):
            yield Tick()
        yield self.endB_link_error_clear.eq(0)
        yield Tick()
        yield self.gate_trigger.eq(1)
        for _ in range(ds_sim_period_to_ticks(150e-6, SRCFREQ)):
            yield Tick()
        yield self.endA_soft_reset.eq(1)
        yield Tick()
        yield self.endA_soft_reset.eq(0)
        for _ in range(ds_sim_period_to_ticks(150e-6, SRCFREQ)):
            yield Tick()

    def test_stress(self):
        self.sim.add_process(self._run)

        vcd = get_vcd_filename()
        gtkw = get_gtkw_filename()
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.ports()):
            self.sim.run()


if __name__ == "__main__":
    unittest.main()
