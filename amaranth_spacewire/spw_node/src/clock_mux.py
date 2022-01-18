from amaranth import *
from amaranth.sim import Simulator
from .clock_divider import ClockDivider

#https://vlsitutorials.com/glitch-free-clock-mux/

class ClockMux(Elaboratable):
    def __init__(self):
        self.i_clka = Signal()
        self.i_clkb = Signal()
        self.i_sel = Signal()
        self.o_clk = Signal()

    def elaborate(self, platform):
        m = Module()

        and_1 = Signal()
        and_1_reg_1 = Signal()
        and_1_reg_2 = Signal()
        and_1_reg_3 = Signal()
        and_1_out = Signal()
        and_2 = Signal()
        and_2_reg_1 = Signal()
        and_2_reg_2 = Signal()
        and_2_reg_3 = Signal()
        and_2_out = Signal()

        m.domains += ClockDomain("clka", local=True)
        m.domains += ClockDomain("clkb", local=True)

        m.d.comb += [
            ClockSignal("clka").eq(self.i_clka),
            ClockSignal("clkb").eq(self.i_clkb)
        ]

        m.d.clka += [
            and_1_reg_1.eq(and_1),
            and_1_reg_2.eq(and_1_reg_1),
            and_1_reg_3.eq(and_1_reg_2)
        ]

        m.d.clkb += [
            and_2_reg_1.eq(and_2),
            and_2_reg_2.eq(and_2_reg_1),
            and_2_reg_3.eq(and_2_reg_2)
        ]

        m.d.comb += [
            and_1.eq(~self.i_sel & ~and_2_reg_3),
            and_2.eq(self.i_sel & ~and_1_reg_3),
            and_1_out.eq(and_1_reg_3 & ClockSignal("clka")),
            and_2_out.eq(and_2_reg_3 & ClockSignal("clkb")),
            self.o_clk.eq(and_1_out | and_2_out)
        ]

        return m

    def ports(self):
        return [self.i_sel, self.o_clk]


if __name__ == '__main__':
    SRCFREQ = 10e6
    LOWFREQ_1 = 5e6
    LOWFREQ_2 = 2e6

    i_sel = Signal()

    m = Module()
    m.submodules.div1 = div1 = ClockDivider(SRCFREQ, LOWFREQ_1)
    m.submodules.div2 = div2 = ClockDivider(SRCFREQ, LOWFREQ_2)
    m.submodules.mux = mux = ClockMux()

    m.d.comb += [
        mux.i_clka.eq(div1.o),
        mux.i_clkb.eq(div2.o),
        mux.i_sel.eq(i_sel)
    ]

    sim = Simulator(m)
    sim.add_clock(1/SRCFREQ)

    def test():
        yield i_sel.eq(0)
        for _ in range(100):
            yield
        yield i_sel.eq(1)
        for _ in range(100):
            yield
        yield i_sel.eq(0)
        for _ in range(100):
            yield

    sim.add_sync_process(test)

    with sim.write_vcd("vcd/clock_mux.vcd", "gtkw/clock_mux.gtkw", traces=mux.ports()):
        sim.run()