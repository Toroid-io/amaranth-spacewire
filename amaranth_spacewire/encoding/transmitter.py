import enum
from amaranth import *
from amaranth_spacewire.encoding.ds_shift_registers import DSOutputCharSR
from amaranth_spacewire.encoding.ds_encoder import DSEncoder
from amaranth_spacewire.misc.clock_divider import ClockDivider
from amaranth_spacewire.misc.clock_mux import ClockMux
from amaranth_spacewire.misc.constants import CHAR_ESC, CHAR_FCT, CHAR_EOP, CHAR_EEP
from amaranth_spacewire.misc.states import TransmitterState


class WrongSignallingRate(Exception):
    def __init__(self, message):
        self.message = message


class WrongSourceFrequency(Exception):
    def __init__(self, message):
        self.message = message


class Transmitter(Elaboratable):
    TX_FREQ_RESET = 10e6
    MIN_TX_FREQ_USER = 2e6

    def __init__(self, srcfreq, rstfreq=TX_FREQ_RESET, txfreq=TX_FREQ_RESET):
        self.data = Signal()
        self.strobe = Signal()
        self.enable = Signal()
        self.switch_user_tx_freq = Signal()
        self.char = Signal(9)
        self.send = Signal()
        self.sent_n_char = Signal()
        self.send_fct = Signal()
        self.sent_fct = Signal()
        self.sent_null = Signal()
        self.ready = Signal()

        self._srcfreq = srcfreq
        self._rstfreq = rstfreq
        self._txfreq = txfreq

        if txfreq < Transmitter.MIN_TX_FREQ_USER:
            raise WrongSignallingRate("Signalling rate must be at least 2 Mb/s (provided {0} Mb/s)".format(txfreq/1e6))
        elif srcfreq < 2 * rstfreq:
            raise WrongSourceFrequency("The source frequency must be at least 2 times the reset transmit frequency. Expected > {0}, given {1}".format(2 * Transmitter.rstfreq, srcfreq))
        elif srcfreq < 2 * txfreq:
            raise WrongSourceFrequency("The source frequency must be at least 2 times the transmit frequency. Expected > {0}, given {1}".format(2 * txfreq, srcfreq))

    def elaborate(self, platform):
        m = Module()

        m.submodules.tr_clk_reset = tr_clk_reset = ClockDivider(self._srcfreq, self._rstfreq)
        m.submodules.tr_clk_user = tr_clk_user = ClockDivider(self._srcfreq, self._txfreq)
        m.submodules.tr_clk_mux = tr_clk_mux = ClockMux()
        m.domains.tx = ClockDomain("tx", local=True)
        m.submodules.encoder = encoder = DomainRenamer("tx")(DSEncoder())
        m.submodules.sr = sr = DomainRenamer("tx")(DSOutputCharSR())

        parity_control = Signal()
        parity_data = Signal()
        # One tx clock delay to hold d/s signals at reset
        encoder_reset = Signal(reset=1)
        encoder_reset_feedback_1 = Signal()
        encoder_reset_feedback_2 = Signal()

        m.d.comb += [
            encoder.i_d.eq(sr.o_output),
            encoder.i_reset.eq(encoder_reset),
            encoder.i_en.eq(sr.o_active),
            sr.i_reset.eq(encoder_reset),
            self.data.eq(encoder.o_d),
            self.strobe.eq(encoder.o_s),
            tr_clk_mux.i_sel.eq(self.switch_user_tx_freq),
            tr_clk_mux.i_clk_a.eq(tr_clk_reset.o),
            tr_clk_mux.i_clk_b.eq(tr_clk_user.o),
            ClockSignal("tx").eq(tr_clk_mux.o_clk)
        ]

        m.d.tx += [encoder_reset_feedback_1.eq(encoder_reset), encoder_reset_feedback_2.eq(encoder_reset_feedback_1)]

        with m.If(~self.enable):
            m.d.sync += encoder_reset.eq(1)
        with m.Elif(encoder_reset_feedback_2):
            m.d.sync += encoder_reset.eq(0)

        with m.FSM() as tr_fsm:
            with m.State(TransmitterState.WAIT):
                with m.If(self.enable & self.ready):
                    with m.If(self.send_fct):
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(CHAR_FCT[0:-1])
                        ]
                        m.d.comb += self.sent_fct.eq(1)
                        m.next = TransmitterState.WAIT_TX_START_CONTROL
                    with m.Elif(self.send):
                        m.d.sync += [
                            sr.i_send_data.eq(~self.char[-1]),
                            sr.i_send_control.eq(self.char[-1]),
                            sr.i_input.eq(self.char[0:-1])
                        ]

                        with m.If(self.char[-1]):
                            m.next = TransmitterState.WAIT_TX_START_CONTROL
                        with m.Else():
                            m.next = TransmitterState.WAIT_TX_START_DATA

                        m.d.comb += self.sent_n_char.eq(1)
                    with m.Else():
                        m.d.sync += [
                            sr.i_send_control.eq(1),
                            sr.i_input.eq(CHAR_ESC[0:-1])
                        ]
                        m.d.comb += self.sent_null.eq(1)
                        m.next = TransmitterState.SEND_NULL_A
            with m.State(TransmitterState.SEND_NULL_A):
                with m.If(~self.enable):
                    m.next = TransmitterState.WAIT
                    m.d.sync += [
                        sr.i_send_control.eq(0),
                        sr.i_send_data.eq(0)
                    ]
                with m.Elif(~sr.o_ready):
                    m.d.sync += sr.i_send_control.eq(0)
                    m.next = TransmitterState.SEND_NULL_B
            with m.State(TransmitterState.SEND_NULL_B):
                with m.If(~self.enable):
                    m.next = TransmitterState.WAIT
                    m.d.sync += [
                        sr.i_send_control.eq(0),
                        sr.i_send_data.eq(0)
                    ]
                with m.Elif(sr.o_ready):
                    m.d.sync += [
                        sr.i_send_control.eq(1),
                        sr.i_input.eq(CHAR_FCT[0:-1])
                    ]
                    m.next = TransmitterState.SEND_NULL_C
            with m.State(TransmitterState.SEND_NULL_C):
                with m.If(~self.enable):
                    m.next = TransmitterState.WAIT
                    m.d.sync += [
                        sr.i_send_control.eq(0),
                        sr.i_send_data.eq(0)
                    ]
                with m.Elif(~sr.o_ready):
                    m.d.sync += sr.i_send_control.eq(0)
                    m.next = TransmitterState.WAIT
            with m.State(TransmitterState.WAIT_TX_START_CONTROL):
                with m.If(~self.enable):
                    m.next = TransmitterState.WAIT
                    m.d.sync += [
                        sr.i_send_control.eq(0),
                        sr.i_send_data.eq(0)
                    ]
                with m.Elif(~sr.o_ready):
                    m.d.sync += sr.i_send_control.eq(0)
                    m.next = TransmitterState.WAIT
            with m.State(TransmitterState.WAIT_TX_START_DATA):
                with m.If(~self.enable):
                    m.next = TransmitterState.WAIT
                    m.d.sync += [
                        sr.i_send_control.eq(0),
                        sr.i_send_data.eq(0)
                    ]
                with m.Elif(~sr.o_ready):
                    m.d.sync += sr.i_send_data.eq(0)
                    m.next = TransmitterState.WAIT

            m.d.comb += self.ready.eq(tr_fsm.ongoing(TransmitterState.WAIT) & sr.o_ready & encoder.o_ready & ~encoder_reset)

        return m

    def ports(self):
        return [
            self.enable,
            self.switch_user_tx_freq,
            self.char,
            self.send,
            self.send_fct,
            self.sent_fct,
            self.sent_null,
            self.ready,
            self.data,
            self.strobe,
        ]
