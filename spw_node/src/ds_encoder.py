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


if __name__ == '__main__':
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
    with simenc.write_vcd("vcd/ds_encoder.vcd", "gtkw/ds_encoder.gtkw", traces=enc.ports()):
        simenc.run()
