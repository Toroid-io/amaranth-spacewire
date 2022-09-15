import enum

from amaranth import *

from amaranth_spacewire.datalink.fsm import DataLinkState


class FlowControlManager(Elaboratable):
    MAX_CREDIT = 56

    def __init__(self):
        self.send_fct = Signal()
        self.got_fct = Signal()
        self.sent_fct = Signal()
        self.credit_error = Signal()
        self.got_n_char = Signal()
        self.sent_n_char = Signal()
        self.link_state = Signal(DataLinkState)
        self.tx_credit = Signal(range(FlowControlManager.MAX_CREDIT + 1))
        self.rx_credit = Signal(range(FlowControlManager.MAX_CREDIT + 1))
        self.tx_ready = Signal()

        self.rx_fifo_r_level = Signal(range(56 + 1))

    def elaborate(self, platform):
        m = Module()
        
        rx_tokens = Signal(range(FlowControlManager.MAX_CREDIT//8 + 1), reset=7)
        
        # Credit error
        with m.If(~(self.link_state == DataLinkState.RUN)
                  | self.credit_error):
            m.d.sync += self.credit_error.eq(0)
        with m.Elif(self.got_fct & (self.tx_credit == FlowControlManager.MAX_CREDIT)):
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
            m.d.comb += rx_tokens.eq((56 - self.rx_credit - self.rx_fifo_r_level) // 8)
        
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
            self.rx_fifo_r_level,
        ]
