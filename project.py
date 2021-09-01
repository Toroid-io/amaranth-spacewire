from nmigen import *
from nmigen.sim import Simulator
from nmigen_boards.de0_nano import DE0NanoPlatform

from clk_div import ClockDivider
from ds import DSDecoder, DSEncoder
from pulse_generator import PulseGenerator
from store_enable import DSStoreEnable


class Receiver(Elaboratable):
    def __init__(self):
        self.i_d_enc = Signal()
        self.i_s_enc = Signal()
        self.o_d = Signal()
        self.o_store_en = Signal()

    def elaborate(self, platform):
        o_clk_decoded = Signal()
        o_d_decoded = Signal()

        m = Module()

        clk_div = ClockDivider(50e6, 3)
        m.submodules += clk_div
        m.domains += ClockDomain(name="store")
        m.d.comb += ClockSignal("store").eq(clk_div.o)

        ds_decoder = DSDecoder()
        m.submodules += ds_decoder
        m.d.comb += [
            ds_decoder.i_d.eq(self.i_d_enc),
            ds_decoder.i_s.eq(self.i_s_enc),
            o_d_decoded.eq(ds_decoder.o_d),
            o_clk_decoded.eq(ds_decoder.o_clk_ddr)
        ]

        ds_store_en = DomainRenamer("store")(DSStoreEnable())
        m.submodules += ds_store_en
        m.d.comb += [
            ds_store_en.i_d.eq(o_d_decoded),
            ds_store_en.i_clk_ddr.eq(o_clk_decoded),
            self.o_d.eq(ds_store_en.o_d),
            self.o_store_en.eq(ds_store_en.o_store_en)
        ]

        return m

    def ports(self):
        return [self.i_d_enc, self.i_s_enc, self.o_d, self.o_store_en]


class Transmitter(Elaboratable):
    def __init__(self):
        self.i_d = Signal()
        self.o_d = Signal()
        self.o_s = Signal()

    def elaborate(self, platform):
        m = Module()

        clk_div = ClockDivider(50e6, 1)
        m.submodules += clk_div
        m.domains += ClockDomain(name="encoder")
        m.d.comb += ClockSignal("encoder").eq(clk_div.o)

        ds = DomainRenamer("encoder")(DSEncoder())
        m.submodules += ds
        m.d.comb += [
            ds.i_d.eq(self.i_d),
            self.o_d.eq(ds.o_d),
            self.o_s.eq(ds.o_s)
        ]

        return m

    def ports(self):
        return [self.i_d, self.o_d, self.o_s]


class Project(Elaboratable):
    def __init__(self):
        self.i_d = Signal()
        self.o_d_enc = Signal()
        self.o_s_enc = Signal()
        self.o_d_dec = Signal()
        self.o_store_en = Signal()

    def elaborate(self, platform):
        m = Module()
        mr = Module()
        mt = Module()

        tr = Transmitter()
        mt.submodules += tr
        mt.d.comb += [
            tr.i_d.eq(self.i_d),
            self.o_d_enc.eq(tr.o_d),
            self.o_s_enc.eq(tr.o_s)
        ]

        re = Receiver()
        mr.submodules += re
        mr.d.comb += [
            re.i_d_enc.eq(self.o_d_enc),
            re.i_s_enc.eq(self.o_s_enc),
            self.o_store_en.eq(re.o_store_en),
            self.o_d_dec.eq(re.o_d),
        ]

        m.submodules += [mr, mt]

        m.d.comb += [
            self.i_d.eq(platform.request("button")),
            platform.request("led", 0).eq(self.o_d_enc),
            platform.request("led", 1).eq(self.o_s_enc),
            platform.request("led", 2).eq(self.o_d_dec),
            platform.request("led", 3).eq(self.o_store_en),
        ]

        return m

    def ports(self):
        return [self.i_d, self.o_d_enc, self.o_s_enc, self.o_d_dec, self.o_store_en]


if __name__ == "__main__":
    pl = DE0NanoPlatform()
    pl.build(Project(), do_program=True)