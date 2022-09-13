import unittest

from amaranth import *
from amaranth.sim import Simulator, Settle

from amaranth_spacewire.datalink.fsm import DataLinkState
from amaranth_spacewire.datalink.flow_control_manager import FlowControlManager
from amaranth_spacewire.misc.constants import CHAR_EEP
from amaranth_spacewire.tests.spw_test_utils import *

SRCFREQ = 20e6

def add_fcm(test):
    m = Module()
    m.submodules.fcm = test.fcm = FlowControlManager()
    test.sim = Simulator(m)
    test.sim.add_clock(1/SRCFREQ)


class Test(unittest.TestCase):
    def setUp(self):
        add_fcm(self)
    
    def stimuli(self):
        yield self.fcm.got_fct.eq(0)
        yield self.fcm.sent_fct.eq(0)
        yield self.fcm.got_n_char.eq(0)
        yield self.fcm.sent_n_char.eq(0)
        yield self.fcm.link_state.eq(0)
        yield self.fcm.tx_ready.eq(0)
        yield self.fcm.rx_fifo_r_rdy.eq(0)
        yield self.fcm.rx_fifo_r_en.eq(0)

        yield self.fcm.link_state.eq(DataLinkState.RUN)
        yield self.fcm.got_fct.eq(1)

        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        
        assert(yield self.fcm.credit_error == 0)
        yield Tick()
        assert(yield self.fcm.credit_error == 1)
        
    def test_fcm(self):
        self.sim.add_process(self.stimuli)

        vcd = get_vcd_filename("credit_error_tx")
        gtkw = get_gtkw_filename("credit_error_tx")
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.fcm.ports()):
            self.sim.run()


class Test(unittest.TestCase):
    def setUp(self):
        add_fcm(self)
    
    def stimuli(self):
        yield self.fcm.got_fct.eq(0)
        yield self.fcm.sent_fct.eq(0)
        yield self.fcm.got_n_char.eq(0)
        yield self.fcm.sent_n_char.eq(0)
        yield self.fcm.link_state.eq(0)
        yield self.fcm.tx_ready.eq(0)
        yield self.fcm.rx_fifo_r_rdy.eq(0)
        yield self.fcm.rx_fifo_r_en.eq(0)

        yield self.fcm.link_state.eq(DataLinkState.RUN)
        yield self.fcm.tx_ready.eq(1)
        yield Tick()
        
        yield Tick()
        assert(yield self.fcm.rx_credit == 0)
        assert(yield self.fcm.send_fct)

        yield Tick()
        
        yield self.fcm.sent_fct.eq(1)
        yield Tick()
        yield self.fcm.sent_fct.eq(0)
        yield Tick()
        assert(yield self.fcm.rx_credit == 8)
        assert(yield self.fcm.send_fct)

        yield self.fcm.sent_fct.eq(1)
        yield Tick()
        
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()

        assert(yield self.fcm.rx_credit == 56)

        yield Tick()
        assert(yield self.fcm.send_fct == 0)
        assert(yield self.fcm.credit_error == 1)

    def test_fcm(self):
        self.sim.add_process(self.stimuli)

        vcd = get_vcd_filename("credit_error_rx")
        gtkw = get_gtkw_filename("credit_error_rx")
        create_sim_output_dirs(vcd, gtkw)

        print(gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.fcm.ports()):
            self.sim.run()
            
            
class Test(unittest.TestCase):
    def setUp(self):
        add_fcm(self)
    
    def stimuli(self):
        yield self.fcm.got_fct.eq(0)
        yield self.fcm.sent_fct.eq(0)
        yield self.fcm.got_n_char.eq(0)
        yield self.fcm.sent_n_char.eq(0)
        yield self.fcm.link_state.eq(0)
        yield self.fcm.tx_ready.eq(0)
        yield self.fcm.rx_fifo_r_rdy.eq(0)
        yield self.fcm.rx_fifo_r_en.eq(0)

        yield self.fcm.link_state.eq(DataLinkState.RUN)
        yield self.fcm.tx_ready.eq(1)
        yield Tick()
        
        yield Tick()
        assert(yield self.fcm.rx_credit == 0)
        assert(yield self.fcm.send_fct)

        yield Tick()
        
        yield self.fcm.sent_fct.eq(1)
        yield Tick()
        yield Settle()
        assert(yield self.fcm.rx_credit == 8)
        assert(yield self.fcm.send_fct)

        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield self.fcm.sent_fct.eq(0)
        yield Tick()

        assert(yield self.fcm.rx_credit == 56)

        yield Tick()
        assert(yield self.fcm.send_fct == 0)
        assert(yield self.fcm.credit_error == 0)
        
        yield self.fcm.got_fct.eq(1)
        yield Tick()
        yield Settle()
        assert(yield self.fcm.tx_credit == 8)
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Tick()
        yield Settle()
        assert(yield self.fcm.tx_credit == 56)

        yield self.fcm.got_fct.eq(0)
        yield Tick()
        yield Settle()
        assert(yield self.fcm.credit_error == 0)
        
        # At this point we have
        # - rx_credit == 56
        # - rx_token == 0
        # - tx_credit == 56
        
        ###################################
        # Receive 8 chars and read 8 chars
        ###################################
        yield self.fcm.got_n_char.eq(1)
        yield Tick()
        yield Settle()
        assert(yield self.fcm.rx_credit == 55)
        yield self.fcm.rx_fifo_r_rdy.eq(1)
        for _ in range(7):
            yield self.fcm.rx_fifo_r_level.eq(self.fcm.rx_fifo_r_level + 1)
            yield Tick()
        yield Settle()
        assert(yield self.fcm.rx_credit == 48)
        assert(yield self.fcm.send_fct == 0)

        yield self.fcm.got_n_char.eq(0)
        yield self.fcm.rx_fifo_r_level.eq(self.fcm.rx_fifo_r_level + 1)
        yield Tick()
        yield Settle()
        
        yield self.fcm.rx_fifo_r_en.eq(1)
        yield Tick()
        yield Settle()
        for _ in range(7):
            yield self.fcm.rx_fifo_r_level.eq(self.fcm.rx_fifo_r_level - 1)
            yield Tick()
        yield Settle()
        assert(yield self.fcm.rx_credit == 48)
        assert(yield self.fcm.send_fct == 0)
        yield self.fcm.rx_fifo_r_level.eq(self.fcm.rx_fifo_r_level - 1)
        yield self.fcm.rx_fifo_r_rdy.eq(0)
        yield Tick()
        yield Settle()
        yield self.fcm.rx_fifo_r_en.eq(0)
        assert(yield self.fcm.rx_credit == 48)
        assert(yield self.fcm.send_fct == 1)
        
        ###################################
        # Verify idle state
        ###################################
        yield Tick()
        yield self.fcm.sent_fct.eq(1)
        yield Tick()
        yield Settle()
        yield self.fcm.sent_fct.eq(0)
        yield Tick()
        yield Settle()
        assert(yield self.fcm.tx_credit == 56)
        assert(yield self.fcm.credit_error == 0)

        ###################################
        # Receive 8 chars and read 8 chars
        # Read FIFO at the same time as bytes are received
        ###################################
        yield self.fcm.got_n_char.eq(1)
        yield Tick()
        yield Settle()
        assert(yield self.fcm.rx_credit == 55)
        yield self.fcm.rx_fifo_r_rdy.eq(1)
        yield self.fcm.rx_fifo_r_level.eq(1)
        yield Tick()
        yield Settle()
        # Read signal reacts one cycle later, but another character got in the FIFO
        yield self.fcm.rx_fifo_r_en.eq(1)
        yield self.fcm.rx_fifo_r_level.eq(2)
        for _ in range(6):
            # Read enable at the same time as a store, so r_level does not change
            yield Tick()
        yield Settle()
        assert(yield self.fcm.rx_credit == 48)
        assert(yield self.fcm.send_fct == 0)

        yield self.fcm.got_n_char.eq(0)
        # Read 7th char
        yield self.fcm.rx_fifo_r_level.eq(1)
        yield Tick()
        yield Settle()

        # Read last char
        yield self.fcm.rx_fifo_r_level.eq(0)
        yield self.fcm.rx_fifo_r_rdy.eq(0)
        yield Tick()
        yield Settle()
        
        assert(yield self.fcm.rx_credit == 48)
        assert(yield self.fcm.send_fct == 1)

        ###################################
        # Verify idle state
        ###################################
        yield Tick()
        yield self.fcm.sent_fct.eq(1)
        yield Tick()
        yield Settle()
        yield self.fcm.sent_fct.eq(0)
        yield Tick()
        yield Settle()
        assert(yield self.fcm.tx_credit == 56)
        assert(yield self.fcm.credit_error == 0)

    def test_fcm(self):
        self.sim.add_process(self.stimuli)

        vcd = get_vcd_filename("credit_count")
        gtkw = get_gtkw_filename("credit_count")
        create_sim_output_dirs(vcd, gtkw)

        print(gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.fcm.ports()):
            self.sim.run()

if __name__ == "__main__":
    unittest.main()