from nmigen import *
from nmigen.sim import Simulator, Delay
from spw_node.src.spw_receiver import SpWReceiver
from spw_node.test.spw_test_utils import (
    ds_sim_send_d, get_vcd_filename, get_gtkw_filename,
    ds_sim_send_null, ds_sim_send_wrong_null, ds_sim_send_char,
    ds_sim_send_timecode
)

def test_receiver():

    SRCFREQ = 20e6
    dut = SpWReceiver(SRCFREQ)

    sim = Simulator(dut)
    sim.add_clock(1/SRCFREQ)

    def decoder_test():
        yield dut.i_s.eq(0)
        yield dut.i_d.eq(0)
        yield Delay(50e-6)
        for _ in range(30):
            yield from ds_sim_send_null(dut.i_d, dut.i_s)
        yield from ds_sim_send_wrong_null(dut.i_d, dut.i_s)
        yield from ds_sim_send_null(dut.i_d, dut.i_s)
        yield from ds_sim_send_null(dut.i_d, dut.i_s)
        yield from ds_sim_send_char(dut.i_d, dut.i_s, 'A')
        yield from ds_sim_send_char(dut.i_d, dut.i_s, 'N')
        yield from ds_sim_send_char(dut.i_d, dut.i_s, 'D')
        yield from ds_sim_send_char(dut.i_d, dut.i_s, 'R')
        yield from ds_sim_send_char(dut.i_d, dut.i_s, 'E')
        yield from ds_sim_send_char(dut.i_d, dut.i_s, 'S')
        yield from ds_sim_send_null(dut.i_d, dut.i_s)
        yield from ds_sim_send_null(dut.i_d, dut.i_s)
        yield from ds_sim_send_null(dut.i_d, dut.i_s)
        yield from ds_sim_send_timecode(dut.i_d, dut.i_s, 0x30)
        for _ in range(30):
            yield from ds_sim_send_null(dut.i_d, dut.i_s)

    def reset_manage():
        yield dut.i_reset.eq(1)
        for _ in range(25):
            yield
        yield dut.i_reset.eq(0)
        while True:
            if (yield dut.o_parity_error == 1):
                yield dut.i_reset.eq(1)
                yield
                yield dut.i_reset.eq(0)
            yield
            if (yield dut.fsm_state == "READ_HEADER"):
                print('lalal')

    sim.add_process(decoder_test)
    sim.add_sync_process(reset_manage)
    with sim.write_vcd(get_vcd_filename(), get_gtkw_filename(), traces=dut.ports()):
        sim.run_until(2e-3)

def test_6_3_2_a():

    SRCFREQ = 10e6
    dut = SpWReceiver(SRCFREQ)

    sim = Simulator(dut)
    sim.add_clock(1/SRCFREQ)

    def decoder_test():
        yield dut.i_s.eq(0)
        yield dut.i_d.eq(0)
        yield Delay(50e-6)
        for _ in range(30):
            yield from ds_sim_send_null(dut.i_d, dut.i_s)
            #assert (yield dut.o_got_null)

    sim.add_process(decoder_test)
    with sim.write_vcd(get_vcd_filename(), get_gtkw_filename(), traces=dut.ports()):
        sim.run_until(2e-3)
