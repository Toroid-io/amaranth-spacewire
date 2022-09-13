import unittest

from amaranth import *
from amaranth.sim import Simulator, Settle

from amaranth_spacewire.datalink.datalink_layer import DataLinkLayer
from amaranth_spacewire.datalink.fsm import DataLinkState
from amaranth_spacewire.tests.spw_test_utils import *

SRCFREQ = 20e6

def add_dll(test):
    m = Module()
    m.submodules.dll = test.dll = DataLinkLayer(srcfreq=SRCFREQ)
    test.sim = Simulator(m)
    test.sim.add_clock(1/SRCFREQ)

def empty_rx_fifo(dll):
    assert(yield dll.link_state != DataLinkState.ERROR_RESET)
    assert(yield dll.r_rdy)
    
    yield dll.r_en.eq(1)
    while (yield dll.r_rdy):
        yield Tick()
        yield Settle()
    
    yield dll.r_en.eq(0)
    yield Tick()
    yield Settle()
    
def go_to_run(dll):
    yield dll.sent_fct.eq(0)
    yield dll.sent_n_char.eq(0)
    yield dll.sent_null.eq(0)
    yield dll.got_n_char.eq(0)
    yield dll.got_null.eq(0)
    yield dll.got_fct.eq(0)
    yield dll.got_bc.eq(0)


    yield dll.link_disabled.eq(1)
    yield Tick()
    yield Settle()
    assert(yield dll.link_state == DataLinkState.ERROR_RESET)

    yield dll.link_disabled.eq(0)
    yield dll.link_start.eq(1)

    while (yield dll.link_state != DataLinkState.STARTED):
        yield Tick()
        yield Settle()
    
    yield dll.sent_null.eq(1)
    yield dll.got_null.eq(1)
    yield Tick()
    yield Settle()
    yield dll.sent_null.eq(0)
    yield dll.got_null.eq(0)
    yield Tick()
    yield Settle()
    assert(yield dll.link_state == DataLinkState.CONNECTING)

    yield dll.sent_fct.eq(1)
    yield dll.got_fct.eq(1)
    yield Tick()
    yield Settle()
    yield dll.sent_fct.eq(0)
    yield dll.got_fct.eq(0)
    yield Tick()
    yield Settle()
    assert(yield dll.link_state == DataLinkState.RUN)

class Test(unittest.TestCase):
    def setUp(self):
        add_dll(self)
    
    def stimuli(self):
        for _ in range(ds_sim_period_to_ticks(50e-6, SRCFREQ)):
            yield Tick()
        
        yield self.dll.link_start.eq(1)

        yield Tick()
        yield Settle()
        assert(yield self.dll.link_state == DataLinkState.STARTED)

        for _ in range(ds_sim_period_to_ticks(12.8e-6, SRCFREQ)):
            yield Tick()
        yield Settle()
        assert(yield self.dll.link_state == DataLinkState.ERROR_RESET)

        for _ in range(ds_sim_period_to_ticks(6.4e-6, SRCFREQ)):
            yield Tick()
        yield Settle()
        assert(yield self.dll.link_state == DataLinkState.ERROR_WAIT)

        for _ in range(ds_sim_period_to_ticks(12.8e-6, SRCFREQ)):
            yield Tick()
        yield Settle()
        assert(yield self.dll.link_state == DataLinkState.READY)

        yield Tick()
        yield Settle()
        assert(yield self.dll.link_state == DataLinkState.STARTED)
        
        yield self.dll.sent_null.eq(1)
        yield self.dll.got_null.eq(1)
        yield Tick()
        yield Settle()
        assert(yield self.dll.link_state == DataLinkState.CONNECTING)
        
        yield self.dll.sent_null.eq(0)
        yield self.dll.got_null.eq(0)
        yield self.dll.tx_ready.eq(1)
        yield Tick()
        yield Settle()
        assert(yield self.dll.send_fct)

        yield Tick()

        yield self.dll.tx_ready.eq(0)
        yield self.dll.sent_fct.eq(1)
        yield Tick()
        yield Settle()
        assert(yield self.dll.send_fct == 0)

        yield self.dll.sent_fct.eq(0)
        yield self.dll.got_fct.eq(1)
        yield Tick()
        yield Settle()
        assert(yield self.dll.link_state == DataLinkState.RUN)

        yield self.dll.got_fct.eq(0)
        yield Tick()
        yield Settle()
        assert(yield self.dll.link_state == DataLinkState.RUN)
        assert(yield self.dll.link_rx_credit == 8)
        assert(yield self.dll.link_tx_credit == 8)
        
        yield self.dll.sent_n_char.eq(1)
        yield Tick()
        yield Settle()
        assert(yield self.dll.link_tx_credit == 7)
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Settle()
        assert(yield self.dll.link_tx_credit == 0)

        # It takes two cycles to go to ERROR_RESET
        # One to trigger a credit error, another one to actually switch to ERROR_RESET
        yield Tick()
        yield Settle()
        assert(yield self.dll.link_tx_credit == 0)

        yield Tick()
        yield Settle()
        assert(yield self.dll.link_state == DataLinkState.ERROR_RESET)
        
        yield from go_to_run(self.dll)
        
        yield self.dll.got_n_char.eq(1)
        yield Tick()
        yield Settle()
        assert(yield self.dll.link_rx_credit == 7)
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Settle()
        assert(yield self.dll.link_rx_credit == 0)

        yield Tick()
        yield Settle()
        assert(yield self.dll.link_rx_credit == 0)

        yield Tick()
        yield Settle()
        assert(yield self.dll.link_state == DataLinkState.ERROR_RESET)

        yield from go_to_run(self.dll)
        yield from empty_rx_fifo(self.dll)
        yield self.dll.tx_ready.eq(1)
        yield Tick()
        yield Settle()
        yield self.dll.sent_fct.eq(1)
        # From simulation: 6 rx_tokens
        for _ in range(6):
            yield Tick()
        yield self.dll.sent_fct.eq(0)
            
        for _ in range(ds_sim_period_to_ticks(50e-6, SRCFREQ)):
            yield Tick()
        
    def test_datalink_layer(self):
        self.sim.add_process(self.stimuli)

        vcd = get_vcd_filename("dummy")
        gtkw = get_gtkw_filename("dummy")
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.dll.ports()):
            self.sim.run()


if __name__ == "__main__":
    unittest.main()