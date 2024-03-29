from amaranth import *

from amaranth_spacewire.misc.states import DataLinkState
from amaranth_spacewire.misc.constants import MAX_RX_CREDIT, MAX_TX_CREDIT, MAX_TOKENS


class FlowControlManager(Elaboratable):
    def __init__(self, fifo_depth_tokens=7):
        self.send_fct = Signal()
        self.got_fct = Signal()
        self.sent_fct = Signal()
        self.credit_error = Signal()
        self.got_n_char = Signal()
        self.sent_n_char = Signal()
        self.link_state = Signal(DataLinkState)
        self.tx_ready = Signal()

        self.MAX_RX_CREDIT = MAX_RX_CREDIT(fifo_depth_tokens)
        self._fifo_depth = fifo_depth_tokens * 8

        self.rx_fifo_level = Signal(range(self._fifo_depth + 1))
        self.tx_credit = Signal(range(MAX_TX_CREDIT + 1))
        self.rx_credit = Signal(range(self.MAX_RX_CREDIT + 1))

    def elaborate(self, platform):
        m = Module()

        rx_tokens = Signal(range(self.MAX_RX_CREDIT // 8 + 1))
        rx_fifo_level_clamped = Signal(range(self.MAX_RX_CREDIT + 1))

        # Fake FIFO level used to compute tokens
        if self._fifo_depth > self.MAX_RX_CREDIT:
            with m.If((self._fifo_depth - self.rx_fifo_level) > self.MAX_RX_CREDIT):
                m.d.comb += rx_fifo_level_clamped.eq(0)
            with m.Else():
                m.d.comb += rx_fifo_level_clamped.eq(self.rx_fifo_level - self.MAX_RX_CREDIT + 1)
        else:
            m.d.comb += rx_fifo_level_clamped.eq(self.rx_fifo_level)


        # Credit error
        with m.If(~(self.link_state == DataLinkState.RUN)
                  | self.credit_error):
            m.d.sync += self.credit_error.eq(0)
        with m.Elif(self.got_fct & (self.tx_credit == MAX_TX_CREDIT)):
            m.d.sync += self.credit_error.eq(1)
        with m.Elif(self.got_n_char & (self.rx_credit == 0)):
            m.d.sync += self.credit_error.eq(1)
        with m.Elif(self.sent_fct & (rx_tokens == 0)):
            m.d.sync += self.credit_error.eq(1)
        with m.Elif(self.sent_n_char & (self.tx_credit == 0)):
            m.d.sync += self.credit_error.eq(1)

        # TX Credit
        with m.If((~(self.link_state == DataLinkState.CONNECTING) & ~(self.link_state == DataLinkState.RUN))
                  | self.credit_error):
            m.d.sync += self.tx_credit.eq(0)
        with m.Elif(self.got_fct & self.sent_n_char):
            m.d.sync += self.tx_credit.eq(self.tx_credit + 7)
        with m.Elif(self.got_fct):
            m.d.sync += self.tx_credit.eq(self.tx_credit + 8)
        with m.Elif(self.sent_n_char & (self.tx_credit > 0)):
            m.d.sync += self.tx_credit.eq(self.tx_credit - 1)

        # RX Credit
        with m.If((~(self.link_state == DataLinkState.CONNECTING) & ~(self.link_state == DataLinkState.RUN))
                  | self.credit_error):
            m.d.sync += self.rx_credit.eq(0)
        with m.Elif(self.sent_fct & self.got_n_char):
            m.d.sync += self.rx_credit.eq(self.rx_credit + 7)
        with m.Elif(self.sent_fct):
            m.d.sync += self.rx_credit.eq(self.rx_credit + 8)
        with m.Elif(self.got_n_char & (self.rx_credit > 0)):
            m.d.sync += self.rx_credit.eq(self.rx_credit - 1)

        # Send FCT logic
        with m.If(((self.link_state == DataLinkState.CONNECTING) | (self.link_state == DataLinkState.RUN))
                  & (rx_tokens > 0) & self.tx_ready):
            m.d.comb += self.send_fct.eq(1)

        # RX tokens
        with m.If((~(self.link_state == DataLinkState.CONNECTING) & ~(self.link_state == DataLinkState.RUN))
                  | self.credit_error):
            m.d.comb += rx_tokens.eq(0)
        with m.Else():
            m.d.comb += rx_tokens.eq((self.MAX_RX_CREDIT - self.rx_credit - rx_fifo_level_clamped) // 8)

        return m

    def ports(self):
        return [
            self.send_fct,
            self.got_fct,
            self.sent_fct,
            self.credit_error,
            self.got_n_char,
            self.sent_n_char,
            self.link_state,
            self.tx_credit,
            self.rx_credit,
            self.tx_ready,
            self.rx_fifo_level,
        ]
