from nmigen import *
from nmigen.utils import bits_for
from nmigen.sim import Simulator, Delay


class DSDecoder(Elaboratable):
    def __init__(self):
        self.i_d = Signal()
        self.i_s = Signal()
        self.o_d = Signal()
        self.o_clk_ddr = Signal()

    def elaborate(self, platform):
        stable_ds_even = Signal()
        stable_ds_odd = Signal()
        stable_xor = Signal()
        stable_d = Signal()
        # Decoding following "RACE C ONDITION FREE SPACEWIRE DECODER FOR FPGA"
        # http://2010.spacewire-conference.org/proceedings/Papers/Components/Nomachi.pdf

        m = Module()

        # Stabilize signals

        # Extended DS even
        with m.If((self.i_d == 0) & (self.i_s == 0)):
            m.d.sync += stable_ds_even.eq(0)
        with m.Elif((self.i_d == 1) & (self.i_s == 1)):
            m.d.sync += stable_ds_even.eq(1)

        # Extended DS odd
        with m.If((self.i_d == 1) & (self.i_s == 0)):
            m.d.sync += stable_ds_odd.eq(1)
        with m.Elif((self.i_d == 0) & (self.i_s == 1)):
            m.d.sync += stable_ds_odd.eq(0)

        # Recovered clock
        m.d.sync += stable_xor.eq(self.i_d ^ self.i_s)

        # DDR handling
        with m.If(stable_xor == 0):
            m.d.comb += stable_d.eq(stable_ds_odd)
        with m.Else():
            m.d.comb += stable_d.eq(stable_ds_even)

        # Add one register to avoid metastability
        m.d.sync += self.o_clk_ddr.eq(stable_xor)
        m.d.sync += self.o_d.eq(stable_d)

        return m

    def ports(self):
        return [self.i_d, self.i_s, self.o_d, self.o_clk_ddr]


if __name__ == '__main__':
    i_d_dec = Signal()
    i_s_dec = Signal()

    mdec = Module()
    mdec.submodules.dec = dec = DSDecoder()
    mdec.d.comb += dec.i_d.eq(i_d_dec)
    mdec.d.comb += dec.i_s.eq(i_s_dec)

    simdec = Simulator(mdec)
    simdec.add_clock(0.5e-6)

    def ds_set(d, s):
        yield i_d_dec.eq(d)
        yield i_s_dec.eq(s)
        yield Delay(1e-6)

    def ds_send_null():
        yield from ds_set(0,1)
        yield from ds_set(1,1)
        yield from ds_set(1,0)
        yield from ds_set(1,1)
        yield from ds_set(0,1)
        yield from ds_set(1,1)
        yield from ds_set(0,1)
        yield from ds_set(0,0)

    def decoder_test():
        yield from ds_send_null()
        yield from ds_send_null()
        yield from ds_send_null()

    simdec.add_process(decoder_test)
    with simdec.write_vcd("vcd/ds_decoder.vcd", "gtkw/ds_decoder.gtkw", traces=dec.ports()):
        simdec.run()
