from nmigen import *
from nmigen.utils import bits_for
from nmigen.sim import Simulator, Delay


class DSEncoder(Elaboratable):
    def __init__(self):
        self.i_reset = Signal()
        self.i_d = Signal()
        self.o_d = Signal()
        self.o_s = Signal()

    def elaborate(self, platform):
        m = Module()

        with m.If(self.i_reset == 1):
            m.d.sync += [
                self.o_d.eq(0),
                self.o_s.eq(0)
            ]
        with m.Else():
            m.d.sync += self.o_d.eq(self.i_d)
            with m.If(self.o_d == self.i_d):
                m.d.sync += self.o_s.eq(~self.o_s)

        return m

    def ports(self):
        return [self.i_d, self.o_d, self.o_s]


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
            m.d.comb += self.o_d.eq(stable_ds_odd)
        with m.Else():
            m.d.comb += self.o_d.eq(stable_ds_even)

        m.d.comb += self.o_clk_ddr.eq(stable_xor)

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
    with simdec.write_vcd("ds_decoder.vcd", "ds_decoder.gtkw", traces=dec.ports()):
        simdec.run()

    i_d_enc = Signal()

    menc = Module()
    menc.submodules.enc = enc = DSEncoder()
    menc.d.comb += enc.i_d.eq(i_d_enc)

    simenc = Simulator(menc)
    simenc.add_clock(1e-6)

    def send_data(d):
        yield i_d_enc.eq(d)
        yield

    def process_enc():
        yield from send_data(0)
        yield from send_data(1)
        yield from send_data(0)
        yield from send_data(1)
        yield from send_data(1)
        yield from send_data(1)
        yield from send_data(0)
        yield from send_data(1)
        yield from send_data(0)

    simenc.add_sync_process(process_enc)
    with simenc.write_vcd("ds_encoder.vcd", "ds_encoder.gtkw", traces=enc.ports()):
        simenc.run()
