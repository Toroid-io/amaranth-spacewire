from nmigen import *
from nmigen.sim import Simulator
from ds_delay import DSDelay
from ds_sim_utils import *

class DSDisconnect(Elaboratable):
    def __init__(self, srcfreq):
        self.i_reset = Signal()
        self.i_store_en = Signal()
        self.o_disconnected = Signal()
        self._srcfreq = srcfreq

    def elaborate(self, platform):
        m = Module()

        m.submodules.delay = delay = DSDelay(self._srcfreq, 850e-9, strategy='at_most')

        m.d.comb += [
            delay.i_start.eq(1),
            self.o_disconnected.eq(delay.o_elapsed)
        ]

        with m.FSM() as fsm:
            with m.State("INIT"):
                with m.If(~self.i_reset & self.i_store_en):
                    m.next = "RUN"
                with m.Else():
                    m.d.comb += delay.i_reset.eq(1)
            with m.State("RUN"):
                with m.If(self.i_reset):
                    m.next = "INIT"
                with m.Else():
                    m.d.comb += delay.i_reset.eq(self.i_store_en)
                    m.next = "RUN"

        return m

    def ports(self):
        return [self.i_reset, self.i_store_en, self.o_disconnected]


if __name__ == '__main__':
    srcfreq = 10e6
    i_reset = Signal()
    i_store_en = Signal()

    m = Module()
    m.submodules.disc = disc = DSDisconnect(srcfreq)
    m.d.comb += [
        disc.i_reset.eq(i_reset),
        disc.i_store_en.eq(i_store_en)
    ]

    def test():
        yield i_reset.eq(1)
        for _ in range(ds_sim_period_to_ticks(50e-6, srcfreq)):
            yield
        yield i_reset.eq(0)
        for _ in range(ds_sim_period_to_ticks(800e-9, srcfreq)):
            yield
        yield i_store_en.eq(1)
        for _ in range(ds_sim_period_to_ticks(900e-9, srcfreq)):
            yield
        yield i_store_en.eq(0)
        for _ in range(ds_sim_period_to_ticks(850e-9, srcfreq)):
            yield
        for _ in range(100):
            yield

    sim = Simulator(m)
    sim.add_clock(1/srcfreq)
    sim.add_sync_process(test)

    with sim.write_vcd("ds_disconnect.vcd", "ds_disconnect.gtkw", traces=disc.ports()):
        sim.run()
