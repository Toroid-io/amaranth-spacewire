from amaranth import *
from amaranth.utils import bits_for
from amaranth.sim import Simulator, Delay


class DSDecoder(Elaboratable):
    """Decode a Data/Strobe signal into Data/Clock.

    Decoding following "RACE CONDITION FREE SPACEWIRE DECODER FOR FPGA"
    http://2010.spacewire-conference.org/proceedings/Papers/Components/Nomachi.pdf

    Attributes
    ----------
    i_d : Signal(1), in
        Data signal from the Data/Strobe pair.
    i_s : Signal(1), in
        Strobe signal from the Data/Strobe pair.
    o_d : Signal(1), out
        Data signal from the output Data/Clock pair. The changes of this signal are in
        sync with the DDR change in ``o_clk_ddr``.
    o_clk_ddr : Signal(1), out
        DDR Clock from the output Data/Clock pair. Associated with changes in
        ``o_d``.
    """
    def __init__(self):
        self.i_d = Signal()
        self.i_s = Signal()
        self.o_d = Signal()
        self.o_clk_ddr = Signal()

    def elaborate(self, platform):
        stable_ds_even = Signal()
        stable_ds_odd = Signal()

        m = Module()

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
        m.d.sync += self.o_clk_ddr.eq(self.i_d ^ self.i_s)

        # DDR handling
        with m.If(self.o_clk_ddr == 0):
            m.d.comb += self.o_d.eq(stable_ds_odd)
        with m.Else():
            m.d.comb += self.o_d.eq(stable_ds_even)

        return m

    def ports(self):
        return [self.i_d, self.i_s, self.o_d, self.o_clk_ddr]
