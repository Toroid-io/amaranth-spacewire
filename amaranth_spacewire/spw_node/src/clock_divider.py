from amaranth import *
from amaranth.utils import bits_for
from amaranth.sim import Simulator


def _divisor(freq_in, freq_out, max_ppm=None):
    """Adapted from a clock divider found on the Glasgow board gateware.
    """
    divisor = freq_in // freq_out
    if divisor <= 0:
        raise ArgumentError("output frequency is too high")

    ppm = 1000000 * ((freq_in / divisor) - freq_out) / freq_out
    if max_ppm is not None and ppm > max_ppm:
        raise ArgumentError("output frequency deviation is too high")

    return divisor


class ClockDivider(Elaboratable):
    """Generate a clock from a base frequency.

    Parameters:
    ----------
    i_freq : int
        Source frequency in Hz.
    o_freq : int
        Target frequency in Hz.

    Attributes
    ----------
    o : Signal(1), out
        Output clock signal.
    """
    def __init__(self, i_freq, o_freq):
        self.o = Signal()
        self._n = round(_divisor(i_freq, o_freq))

    def elaborate(self, platform):
        m = Module()

        counter = Signal(bits_for(self._n - 1), reset=self._n - 1)

        with m.If(counter == self._n - 1):
            m.d.sync += self.o.eq(~self.o)
        with m.If(counter == self._n//2 - 1):
            m.d.sync += self.o.eq(~self.o)

        with m.If(counter == self._n - 1):
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