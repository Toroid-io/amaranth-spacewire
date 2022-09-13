import unittest

from amaranth import *
from amaranth.sim import Simulator, Settle

from amaranth_spacewire.encoding.transmitter import Transmitter
from amaranth_spacewire.misc.constants import *
from amaranth_spacewire.tests.spw_test_utils import *

SRCFREQ = 20e6
TXFREQ = Transmitter.TX_FREQ_RESET


def add_tr(test):
    m = Module()
    m.submodules.tr = test.tr = Transmitter(SRCFREQ)
    test.sim = Simulator(m)
    test.sim.add_clock(1/SRCFREQ)
    test.sim.add_clock(1/TXFREQ, domain=ClockDomain("tx"))

class Test(unittest.TestCase):
    def setUp(self):
        add_tr(self)
    
    def stimuli(self):
        yield from ds_sim_delay(50e-6, SRCFREQ)
        assert(yield self.tr.data == 0)
        assert(yield self.tr.strobe == 0)
        
        yield self.tr.enable.eq(1)
        yield Tick()
        yield Settle()
        yield from ds_sim_ticks_tx(20, SRCFREQ, TXFREQ)
        yield self.tr.enable.eq(0)
        yield Tick()
        yield Settle()
        yield from ds_sim_ticks_tx(20, SRCFREQ, TXFREQ)
        yield self.tr.enable.eq(1)
        yield Tick()
        yield Settle()
        yield from ds_sim_ticks_tx(200, SRCFREQ, TXFREQ)
        
    def test_transmitter(self):
        self.sim.add_process(self.stimuli)

        vcd = get_vcd_filename("nulls")
        gtkw = get_gtkw_filename("nulls")
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.tr.ports()):
            self.sim.run()


class Test(unittest.TestCase):
    def setUp(self):
        add_tr(self)
    
    def stimuli(self):
        yield from ds_sim_delay(50e-6, SRCFREQ)
        assert(yield self.tr.data == 0)
        assert(yield self.tr.strobe == 0)
        
        yield self.tr.enable.eq(1)
        yield from ds_sim_ticks_tx(50, SRCFREQ, TXFREQ)
        
        while (yield self.tr.ready == 0):
            yield Tick()
            yield Settle()
        yield self.tr.send.eq(1)
        yield self.tr.send_fct.eq(1)
        yield self.tr.char.eq(CHAR_EEP)

        yield from ds_sim_ticks_tx(50, SRCFREQ, TXFREQ)

        yield self.tr.send_fct.eq(0)

        yield from ds_sim_ticks_tx(50, SRCFREQ, TXFREQ)

        yield self.tr.send.eq(0)

        yield from ds_sim_ticks_tx(50, SRCFREQ, TXFREQ)
        
    def test_transmitter(self):
        self.sim.add_process(self.stimuli)

        vcd = get_vcd_filename("priorities")
        gtkw = get_gtkw_filename("priorities")
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.tr.ports()):
            self.sim.run()


if __name__ == "__main__":
    unittest.main()