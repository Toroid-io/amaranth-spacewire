from nmigen import *
from nmigen.utils import bits_for
from nmigen.sim import Simulator


def _divisor(freq_in, freq_out, max_ppm=None):
    divisor = freq_in // freq_out
    if divisor <= 0:
        raise ArgumentError("output frequency is too high")

    ppm = 1000000 * ((freq_in / divisor) - freq_out) / freq_out
    if max_ppm is not None and ppm > max_ppm:
        raise ArgumentError("output frequency deviation is too high")

    return divisor


class ClockDivider(Elaboratable):
    def __init__(self, i_freq, o_freq):
        self.o = Signal()
        self.n = round(_divisor(i_freq, o_freq))

    def elaborate(self, platform):
        m = Module()

        counter = Signal(bits_for(self.n - 1), reset=self.n - 1)

        with m.If(counter == self.n - 1):
            m.d.sync += self.o.eq(~self.o)
        with m.If(counter == self.n//2 - 1):
            m.d.sync += self.o.eq(~self.o)

        with m.If(counter == self.n - 1):
            m.d.sync += counter.eq(0)
        with m.Else():
            m.d.sync += counter.eq(counter + 1)

        return m


if __name__ == '__main__':
    dut = ClockDivider(1e6, 0.1e6)
    def test():
        for _ in range(50):
            yield

    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_sync_process(test)
    with sim.write_vcd("vcd/clock_divider.vcd"):
        sim.run()