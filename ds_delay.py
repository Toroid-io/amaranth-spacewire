from nmigen import *
from nmigen.utils import bits_for
from nmigen.sim import Simulator, Delay
import math

def _ticksForDelay(freq, delay, max_ppm=None, strategy='at_most'):
    period = 1/freq
    if strategy == 'at_most':
        ticks = math.floor(delay/period)
    else:
        ticks = math.ceil(delay/period)

    ppm = 1000000 * ((period * ticks) - delay) / delay

    if max_ppm is not None and ppm > max_ppm:
        raise ArgumentError("Ticks deviation is too high")

    if delay == 0 or delay is None or ticks == 0:
        raise ArgumentError("Period is too large for the requested delay")

    return ticks

class DSDelay(Elaboratable):
    def __init__(self, srcfreq, delay, strategy='at_least'):
        self.i_start = Signal()
        self.i_reset = Signal()
        self.o_elapsed = Signal()
        self.o_half_elapsed = Signal()
        self._ticks = _ticksForDelay(srcfreq, delay, strategy=strategy)
        self._strategy = strategy

    def elaborate(self, platform):
        m = Module()

        counter = Signal(bits_for(self._ticks))
        if self._strategy == 'at_least':
            counter_half = math.ceil(self._ticks/2)
        else:
            counter_half = math.floor(self._ticks/2)

        with m.FSM() as fsm:
            with m.State("WAIT"):
                with m.If((self.i_start & ~self.i_reset) == 1):
                    m.next = "DELAY"
                with m.Elif(self.i_reset == 1):
                    m.d.sync += [self.o_elapsed.eq(0), self.o_half_elapsed.eq(0)]
            with m.State("DELAY"):
                with m.If(self.i_reset == 1):
                    m.d.sync += counter.eq(0)
                    m.next = "WAIT"
                with m.Else():
                    with m.If(counter == (counter_half - 1)):
                        m.d.sync += self.o_half_elapsed.eq(1)

                    with m.If(counter == self._ticks - 1):
                        m.d.sync += [
                            counter.eq(0),
                            self.o_elapsed.eq(1)
                        ]
                        m.next = "WAIT"
                    with m.Else():
                        m.d.sync += counter.eq(counter + 1)

        return m

    def ports(self):
        return [self.i_start, self.o_elapsed, self.o_half_elapsed]

if __name__ == '__main__':
    i_start = Signal()
    m = Module()
    m.submodules.delay = delay = DSDelay(1.3e6, 34e-6)
    m.d.comb += delay.i_start.eq(i_start)

    sim = Simulator(m)
    sim.add_clock(1/1.3e6)

    def test():
        for _ in range(20):
            yield
        yield i_start.eq(1)
        yield
        yield
        yield i_start.eq(0)
        while ((yield delay.o_elapsed) == 0):
            yield
        for _ in range(20):
            yield

    sim.add_sync_process(test)
    with sim.write_vcd("delay.vcd", "delay.gtkw", traces=delay.ports()):
        sim.run()