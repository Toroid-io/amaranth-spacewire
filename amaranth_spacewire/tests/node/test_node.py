import unittest

from amaranth import *
from amaranth.sim import Simulator, Settle

from amaranth_spacewire.node_new import Node
from amaranth_spacewire.encoding.transmitter import Transmitter
from amaranth_spacewire.misc.constants import *
from amaranth_spacewire.tests.spw_test_utils import *

SRCFREQ = 40e6
TXFREQ = Transmitter.TX_FREQ_RESET * 2


def add_nodes(test):
    m = Module()
    m.submodules.node_1 = test.node_1 = Node(SRCFREQ, txfreq=TXFREQ)
    m.submodules.node_2 = test.node_2 = Node(SRCFREQ, txfreq=TXFREQ)
    
    m.d.comb += [
        test.node_1.data_input.eq(test.node_2.data_output),
        test.node_1.strobe_input.eq(test.node_2.strobe_output),
        test.node_2.data_input.eq(test.node_1.data_output),
        test.node_2.strobe_input.eq(test.node_1.strobe_output),
    ]
    
    test.sim = Simulator(m)
    test.sim.add_clock(1/SRCFREQ)
    test.sim.add_clock(1/TXFREQ, domain=ClockDomain("tx"))


def send_hello_world(test):
    s = 'Hello World in SpaceWire!'
    vals = [ord(c) for c in s]
    
    yield test.node_1.w_en.eq(1)
    for v in vals:
        while (yield test.node_1.w_rdy == 0):
            yield Tick()
            yield Settle()
        yield test.node_1.w_data.eq(v)
        yield Tick()
        yield Settle()

    while (yield test.node_1.w_rdy == 0):
        yield Tick()
        yield Settle()
    yield test.node_1.w_data.eq(CHAR_EOP)
    yield Tick()
    yield Settle()
    yield test.node_1.w_en.eq(0)


class Test(unittest.TestCase):
    def setUp(self):
        add_nodes(self)
    
    def stimuli(self):
        yield self.node_1.link_disabled.eq(1)
        yield self.node_2.link_disabled.eq(1)
        yield from ds_sim_delay(20e-6, SRCFREQ)
        yield self.node_1.link_disabled.eq(0)
        yield self.node_1.link_start.eq(1)
        
        yield from ds_sim_delay(100e-6, SRCFREQ)

        yield self.node_2.link_disabled.eq(0)
        yield self.node_2.link_start.eq(1)
        
        yield from ds_sim_delay(100e-6, SRCFREQ)
        
        yield self.node_1.w_en.eq(1)
        yield self.node_1.w_data.eq(48)
        while (yield self.node_1.w_rdy != 0):
            yield Tick()
            yield Settle()
        yield self.node_1.w_en.eq(0)
        yield from ds_sim_delay(100e-6, SRCFREQ)

        yield self.node_2.r_en.eq(1)
        yield from ds_sim_delay(50e-6, SRCFREQ)
        
        yield from send_hello_world(self)

        yield from ds_sim_delay(100e-6, SRCFREQ)
        
        yield self.node_1.tx_switch_freq.eq(1)

        for _ in range(5):
            yield from ds_sim_delay(50e-6, SRCFREQ)
            yield from send_hello_world(self)

        yield from ds_sim_delay(50e-6, SRCFREQ)
        
    def test_node(self):
        self.sim.add_process(self.stimuli)

        vcd = get_vcd_filename("init")
        gtkw = get_gtkw_filename("init")
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.node_1.ports() + self.node_2.ports()):
            self.sim.run()


if __name__ == "__main__":
    unittest.main()