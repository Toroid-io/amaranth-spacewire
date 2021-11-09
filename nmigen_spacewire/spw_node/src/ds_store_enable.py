from nmigen import *
from nmigen.sim import Simulator, Delay
from .pulse_generator import PulseGenerator
from .ds_decoder import DSDecoder


class DSStoreEnable(Elaboratable):
    def __init__(self):
        self.i_reset = Signal()
        self.i_d = Signal()
        self.i_clk_ddr = Signal()
        self.o_d = Signal()
        self.o_store_en = Signal()

    def elaborate(self, platform):
        pulse_rising = Signal()
        pulse_falling = Signal()
        internal_clk_ddr = Signal()
        internal_clk_ddr_n = Signal()
        got_first_transition = Signal()

        m = Module()
        with m.If(self.i_reset):
            m.d.comb += internal_clk_ddr.eq(0)
            m.d.comb += internal_clk_ddr_n.eq(0)
            m.d.sync += self.o_store_en.eq(0)
            m.d.sync += got_first_transition.eq(0)
        with m.Else():
            m.d.comb += internal_clk_ddr.eq(self.i_clk_ddr)
            m.d.comb += internal_clk_ddr_n.eq(~self.i_clk_ddr)
            m.d.sync += self.o_store_en.eq(pulse_rising | pulse_falling)
            m.d.sync += self.o_d.eq(self.i_d)
            with m.If(pulse_rising & ~got_first_transition):
                m.d.sync += got_first_transition.eq(1)

        pg_rising = PulseGenerator()
        pg_falling = PulseGenerator()
        m.submodules += [pg_rising, pg_falling]

        m.d.comb += [
            pg_rising.i_en.eq(internal_clk_ddr),
            pg_rising.i_reset.eq(self.i_reset),
            pulse_rising.eq(pg_rising.o_pulse),
            pg_falling.i_en.eq(internal_clk_ddr_n & got_first_transition),
            pg_falling.i_reset.eq(self.i_reset),
            pulse_falling.eq(pg_falling.o_pulse)
        ]

        return m

    def ports(self):
        return [self.i_d, self.i_clk_ddr, self.o_d, self.o_store_en]


if __name__ == '__main__':
    i_d_dec = Signal()
    i_s_dec = Signal()

    m = Module()

    m.submodules.dec = dec = DSDecoder()
    m.d.comb += dec.i_d.eq(i_d_dec)
    m.d.comb += dec.i_s.eq(i_s_dec)

    m.submodules.sten = sten = DSStoreEnable()
    m.d.comb += sten.i_d.eq(dec.o_d)
    m.d.comb += sten.i_clk_ddr.eq(dec.o_clk_ddr)

    def ds_set(d, s):
        yield i_d_dec.eq(d)
        yield i_s_dec.eq(s)
        yield Delay(7.3e-6)

    def ds_send_null():
        yield from ds_set(0,1)
        yield from ds_set(1,1)
        yield from ds_set(1,0)
        yield from ds_set(1,1)
        yield from ds_set(0,1)
        yield from ds_set(1,1)
        yield from ds_set(0,1)
        yield from ds_set(0,0)

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