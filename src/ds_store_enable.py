from nmigen import *
from nmigen.sim import Simulator, Delay
from .pulse_generator import PulseGenerator


class DSStoreEnable(Elaboratable):
    def __init__(self):
        self.i_reset = Signal()
        self.i_d = Signal()
        self.i_clk_ddr = Signal()
        self.o_d = Signal()
        self.o_store_en = Signal()

    def elaborate(self, platform):
        self.pulse_rising = Signal()
        self.pulse_falling = Signal()
        self.reg_clk = Signal()
        self.reg_clk_n = Signal()

        m = Module()
        m.d.sync += self.reg_clk.eq(self.i_clk_ddr)
        m.d.comb += self.reg_clk_n.eq(~self.reg_clk)

        pg_rising = PulseGenerator()
        pg_falling = PulseGenerator()

        m.d.comb += [
            pg_rising.i_en.eq(self.reg_clk),
            self.pulse_rising.eq(pg_rising.o_pulse),
            pg_falling.i_en.eq(self.reg_clk_n),
            self.pulse_falling.eq(pg_falling.o_pulse)
        ]

        m.submodules += [pg_rising, pg_falling]

        with m.If(self.i_reset == 1):
            m.d.comb += self.o_store_en.eq(0)
        with m.Else():
            m.d.comb += self.o_store_en.eq(self.pulse_rising | self.pulse_falling)

        m.d.comb += self.o_d.eq(self.i_d)

        return m

    def ports(self):
        return [self.i_d, self.i_clk_ddr, self.o_d, self.o_store_en]


if __name__ == '__main__':
    i_d = Signal()
    i_clk_ddr = Signal()

    m = Module()
    m.submodules.sten = sten = DSStoreEnable()
    m.d.comb += sten.i_d.eq(i_d)
    m.d.comb += sten.i_clk_ddr.eq(i_clk_ddr)

    def ds_set(d):
        yield i_d.eq(d)
        yield i_clk_ddr.eq(~i_clk_ddr)
        yield Delay(1.7e-6)

    def ds_send_null():
        yield from ds_set(0)
        yield from ds_set(1)
        yield from ds_set(1)
        yield from ds_set(1)
        yield from ds_set(0)
        yield from ds_set(1)
        yield from ds_set(0)
        yield from ds_set(0)

    def test():
        yield sten.i_reset.eq(1)
        yield Delay(10e-6)
        yield sten.i_reset.eq(0)
        yield from ds_send_null()
        yield from ds_send_null()
        yield from ds_send_null()

    sim = Simulator(m)
    sim.add_clock(1e-6)
    sim.add_process(test)

    with sim.write_vcd("vcd/ds_store_enable.vcd", "gtkw/ds_store_enable.gtkw", traces=sten.ports()):
        sim.run()