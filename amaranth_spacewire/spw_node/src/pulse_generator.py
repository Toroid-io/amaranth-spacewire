from amaranth import *
from amaranth.sim import Simulator


class PulseGenerator(Elaboratable):
    def __init__(self):
        self.i_en = Signal()
        self.i_reset = Signal()
        self.o_pulse = Signal()

    def elaborate(self, platform):
        m = Module()

        with m.FSM() as fsm:
            with m.State("IDLE"):
                with m.If(~self.i_reset & self.i_en):
                    m.d.comb += self.o_pulse.eq(1)
                    m.next = "PULSE"
            with m.State("PULSE"):
                with m.If(self.i_reset | ~self.i_en):
                    m.next = "IDLE"

        return m

    def ports(self):
        return [self.i_en, self.o_pulse]


if __name__ == '__main__':
    i_en = Signal()
    i_reset = Signal()
    m = Module()
    m.submodules.pg = pg = PulseGenerator()
    m.d.comb += [
        pg.i_en.eq(i_en),
        pg.i_reset.eq(i_reset)
    ]

    sim = Simulator(m)
    sim.add_clock(1e-6)

    def test():
        yield
        yield
        yield i_en.eq(1)
        yield
        yield
        yield
        yield
        yield i_en.eq(0)
        yield
        yield

    sim.add_sync_process(test)
    with sim.write_vcd("vcd/pulse_generator.vcd", "gtkw/pulse_generator.gtkw", traces=pg.ports()):
        sim.run()