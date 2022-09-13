import unittest

from amaranth import *
from amaranth.sim import Simulator, Settle

from amaranth_spacewire.datalink.recovery_fsm import RecoveryFSM, RecoveryState
from amaranth_spacewire.datalink.fsm import DataLinkState
from amaranth_spacewire.misc.constants import CHAR_EEP
from amaranth_spacewire.tests.spw_test_utils import *

SRCFREQ = 20e6

def add_fsm(test):
    m = Module()
    m.submodules.fsm = test.fsm = RecoveryFSM()
    test.sim = Simulator(m)
    test.sim.add_clock(1/SRCFREQ)


class Test(unittest.TestCase):
    def setUp(self):
        add_fsm(self)
    
    def stimuli(self):
        yield self.fsm.link_state.eq(DataLinkState.RUN)
        yield self.fsm.link_disabled.eq(0)
        yield self.fsm.disconnect_error.eq(0)
        yield self.fsm.parity_error.eq(0)
        yield self.fsm.esc_error.eq(0)
        yield self.fsm.credit_error.eq(0)
        yield self.fsm.tx_fifo_r_en_in.eq(0)
        
        # There is data in the tx fifo
        yield self.fsm.tx_fifo_r_rdy_in.eq(1)
        # The receive FIFO is full
        yield self.fsm.rx_fifo_w_rdy_in.eq(0)
        yield Tick()

        assert(yield self.fsm.recovery_state == RecoveryState.NORMAL)
        
        # Disable the link
        yield self.fsm.link_disabled.eq(1)
        yield Tick()
        
        # Then the state goes to recovery
        yield Tick()
        assert(yield self.fsm.recovery_state == RecoveryState.RECOVERY_DISCARD_TX)

        for _ in range(ds_sim_period_to_ticks(50e-6, SRCFREQ)):
            # And the tx fifo read enable stays high as long as r_rdy is high
            yield Tick()
            assert(yield self.fsm.tx_fifo_r_en_out)

        # No more data to send
        yield self.fsm.tx_fifo_r_rdy_in.eq(0)
        yield Tick()

        # No more data read by the recovery fsm
        assert(yield self.fsm.tx_fifo_r_en_out == 0)
        yield Tick()

        # Then the state goes to ADD_EEP_RX
        assert(yield self.fsm.recovery_state == RecoveryState.RECOVERY_ADD_EEP_RX)

        for _ in range(ds_sim_period_to_ticks(30e-6, SRCFREQ)):
            # Nothing happens until w_rdy is asserted
            assert(yield self.fsm.recovery_state == RecoveryState.RECOVERY_ADD_EEP_RX)
            assert(yield self.fsm.rx_fifo_w_en_out == 0)
            yield Tick()
        
        # Write enable is asserted as soon as there is room in the RX FIFO
        yield self.fsm.rx_fifo_w_rdy_in.eq(1)
        yield Settle()
        assert(yield self.fsm.rx_fifo_w_en_out)
        assert(yield self.fsm.rx_fifo_w_data_out == CHAR_EEP)
        yield Tick()
        yield Tick()

        # Then the state goes to NORMAL
        assert(yield self.fsm.recovery_state == RecoveryState.NORMAL)
        # And the link disabled flag was saved
        assert(yield self.fsm.recovery_error == (1 << 4)) 

    def test_recovery(self):
        self.sim.add_process(self.stimuli)

        vcd = get_vcd_filename("wait_rx_fifo")
        gtkw = get_gtkw_filename("wait_rx_fifo")
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.fsm.ports()):
            self.sim.run()


class Test2(unittest.TestCase):
    def setUp(self):
        add_fsm(self)
    
    def stimuli(self):
        yield self.fsm.link_state.eq(DataLinkState.RUN)
        yield self.fsm.link_disabled.eq(0)
        yield self.fsm.disconnect_error.eq(0)
        yield self.fsm.parity_error.eq(0)
        yield self.fsm.esc_error.eq(0)
        yield self.fsm.credit_error.eq(0)
        yield self.fsm.tx_fifo_r_en_in.eq(0)
        yield self.fsm.tx_fifo_r_data_in.eq(CHAR_EEP)
        
        # There is data in the tx fifo
        yield self.fsm.tx_fifo_r_rdy_in.eq(1)
        # The receive FIFO is not full
        yield self.fsm.rx_fifo_w_rdy_in.eq(1)
        yield Tick()

        assert(yield self.fsm.recovery_state == RecoveryState.NORMAL)
        
        # Disable the link
        yield self.fsm.disconnect_error.eq(1)
        yield Tick()
        
        # Then the state goes to recovery
        yield Tick()
        assert(yield self.fsm.recovery_state == RecoveryState.RECOVERY_DISCARD_TX)

        assert(yield self.fsm.tx_fifo_r_en_out == 0)

        # Because the byte in tx_fifo_r_data_in is an CHAR_EEP, it was sent last and
        # we just go to the next recovery state
        yield Tick()

        # No data read by the recovery fsm
        assert(yield self.fsm.tx_fifo_r_en_out == 0)

        # Then the state goes to ADD_EEP_RX
        assert(yield self.fsm.recovery_state == RecoveryState.RECOVERY_ADD_EEP_RX)

        assert(yield self.fsm.rx_fifo_w_en_out)
        assert(yield self.fsm.rx_fifo_w_data_out == CHAR_EEP)
        yield Tick()
        
        # Then the state goes to NORMAL
        assert(yield self.fsm.recovery_state == RecoveryState.NORMAL)
        # And the link disabled flag was saved
        assert(yield self.fsm.recovery_error == (1 << 0)) 

    def test_recovery(self):
        self.sim.add_process(self.stimuli)

        vcd = get_vcd_filename("no_discard")
        gtkw = get_gtkw_filename("no_discard")
        create_sim_output_dirs(vcd, gtkw)

        with self.sim.write_vcd(vcd, gtkw, traces=self.fsm.ports()):
            self.sim.run()

if __name__ == "__main__":
    unittest.main()