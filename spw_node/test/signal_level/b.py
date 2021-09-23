from nmigen import *
from nmigen.sim import Simulator, Delay, Settle
from spw_node.src.spw_transmitter import SpWTransmitter
from spw_node.test.spw_test_utils import *

def test_6_3_2_b():

    SRCFREQ = 10e6
    BIT_TIME = 0.5e-6
    CHAR_TIME = BIT_TIME * 4

    dut = SpWTransmitter(SRCFREQ, 1/BIT_TIME, debug=True)

    sim = Simulator(dut)
    sim.add_clock(1/SRCFREQ)

    def test():
        yield dut.i_reset.eq(1)
        for _ in range(ds_sim_period_to_ticks(20e-6, SRCFREQ)):
            yield
        yield dut.i_reset.eq(0)
        for _ in range(ds_sim_period_to_ticks(20e-6, SRCFREQ)):
            yield
        yield dut.i_reset.eq(1)
        yield
        yield
        yield dut.i_reset.eq(0)
        for _ in range(ds_sim_period_to_ticks(12e-6, SRCFREQ)):
            yield
        yield dut.i_reset.eq(1)
        yield
        yield dut.i_reset.eq(0)
        while not (yield dut.o_encoder_reset_feedback):
            yield
        for _ in range(ds_sim_period_to_ticks(33e-6, SRCFREQ)):
            yield


    sim.add_sync_process(test)

    with sim.write_vcd(get_vcd_filename(), get_gtkw_filename(), traces=dut.ports()):
        sim.run_until(100e-6)

tests = [test_6_3_2_b]