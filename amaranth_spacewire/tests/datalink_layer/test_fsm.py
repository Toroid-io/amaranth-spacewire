import unittest

from amaranth import *
from amaranth.sim import Simulator, Settle

from amaranth_spacewire.datalink.fsm import DataLinkFSM, DataLinkState
from amaranth_spacewire.tests.spw_test_utils import *

SRCFREQ = 20e6

def add_fsm(test):
    m = Module()
    m.submodules.fsm = test.fsm = DataLinkFSM(srcfreq=SRCFREQ,
                                              transission_delay=12.8e-6)
    test.sim = Simulator(m)
    test.sim.add_clock(1/SRCFREQ)


class ResetLoop(unittest.TestCase):
    def setUp(self):
        add_fsm(self)
    
    def stimuli(self):
        yield self.fsm.link_start.eq(1)
        
        # First simulator rising edge
        yield Tick()

        assert(yield self.fsm.link_state == DataLinkState.ERROR_RESET)
        for _ in range(ds_sim_period_to_ticks(6.4e-6, SRCFREQ)):
            yield Tick()

        assert(yield self.fsm.link_state == DataLinkState.ERROR_WAIT)
        for _ in range(ds_sim_period_to_ticks(12.8e-6, SRCFREQ)):
            yield Tick()

        assert(yield self.fsm.link_state == DataLinkState.READY)
        yield Tick()

        assert(yield self.fsm.link_state == DataLinkState.STARTED)

        for _ in range(ds_sim_period_to_ticks(12.8e-6, SRCFREQ)):
            yield Tick()
        yield Tick()

        assert(yield self.fsm.link_state == DataLinkState.ERROR_RESET)

    def test_fsm(self):
        self.sim.add_process(self.stimuli)

        vcd = get_vcd_filename()
        gtkw = get_gtkw_filename()
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.fsm.ports()):
            self.sim.run()


class ResetInConnecting(unittest.TestCase):
    def setUp(self):
        add_fsm(self)
    
    def stimuli(self):
        yield self.fsm.link_start.eq(1)
        
        # First simulator rising edge
        yield Tick()

        # ErrorReset -> ErrorWait -> Ready
        for _ in range(ds_sim_period_to_ticks(6.4e-6 + 12.8e-6, SRCFREQ)):
            yield Tick()

        assert(yield self.fsm.link_state == DataLinkState.READY)

        # -> Started
        yield self.fsm.got_null.eq(1)
        yield self.fsm.sent_null.eq(1)
        yield Tick()

        assert(yield self.fsm.link_state == DataLinkState.STARTED)

        # -> Connecting
        yield Tick()

        assert(yield self.fsm.link_state == DataLinkState.CONNECTING)

        # -> ErrorReset
        for _ in range(ds_sim_period_to_ticks(12.8e-6, SRCFREQ)):
            yield Tick()

        assert(yield self.fsm.link_state == DataLinkState.ERROR_RESET)

    def test_fsm(self):
        self.sim.add_process(self.stimuli)

        vcd = get_vcd_filename("reset_in_connecting")
        gtkw = get_gtkw_filename("reset_in_connecting")
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.fsm.ports()):
            self.sim.run()


class ResetInConnecting(unittest.TestCase):
    def setUp(self):
        add_fsm(self)
    
    def stimuli(self):
        yield self.fsm.link_start.eq(1)
        
        # First simulator rising edge
        yield Tick()

        # ErrorReset -> ErrorWait -> Ready
        for _ in range(ds_sim_period_to_ticks(6.4e-6 + 12.8e-6, SRCFREQ)):
            yield Tick()

        assert(yield self.fsm.link_state == DataLinkState.READY)

        # -> Started
        yield self.fsm.got_null.eq(1)
        yield self.fsm.sent_null.eq(1)
        yield Tick()

        assert(yield self.fsm.link_state == DataLinkState.STARTED)

        # -> Connecting
        yield self.fsm.got_fct.eq(1)
        yield self.fsm.sent_fct.eq(1)
        yield Tick()

        assert(yield self.fsm.link_state == DataLinkState.CONNECTING)

        # -> RUN
        yield self.fsm.receive_error.eq(1)
        yield Tick()

        assert(yield self.fsm.link_state == DataLinkState.RUN)

        # -> ErrorReset
        yield Tick()

        assert(yield self.fsm.link_state == DataLinkState.ERROR_RESET)

    def test_fsm(self):
        self.sim.add_process(self.stimuli)

        vcd = get_vcd_filename("reset_in_run")
        gtkw = get_gtkw_filename("reset_in_run")
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.fsm.ports()):
            self.sim.run()


if __name__ == "__main__":
    unittest.main()