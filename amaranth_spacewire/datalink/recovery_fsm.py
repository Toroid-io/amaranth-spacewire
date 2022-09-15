import enum

from amaranth import *
from .fsm import DataLinkState
from amaranth_spacewire.misc.constants import CHAR_EEP, CHAR_EOP


class RecoveryState(enum.Enum):
    NORMAL = 0
    RECOVERY_DISCARD_TX = 1
    RECOVERY_ADD_EEP_RX = 2


class RecoveryFSM(Elaboratable):
    def __init__(self):
        self.link_state = Signal(DataLinkState)
        self.link_disabled = Signal()
        self.disconnect_error = Signal()
        self.parity_error = Signal()
        self.esc_error = Signal()
        self.credit_error = Signal()

        self.rx_fifo_w_rdy_in = Signal()
        self.rx_fifo_w_rdy_out = Signal()
        self.rx_fifo_w_en_in = Signal()
        self.rx_fifo_w_en_out = Signal()
        self.rx_fifo_w_data_in = Signal(9)
        self.rx_fifo_w_data_out = Signal(9)

        self.tx_fifo_r_rdy_in = Signal()
        self.tx_fifo_r_rdy_out = Signal()
        self.tx_fifo_r_en_in = Signal()
        self.tx_fifo_r_en_out = Signal()
        self.tx_fifo_r_data_in = Signal(9)
        self.tx_fifo_r_data_out = Signal(9)

        self.recovery_error = Signal(5)

    def elaborate(self, platform):
        m = Module()
        
        input_error = Signal(5)
        last_is_ep = Signal()

        m.d.comb += input_error.eq(Cat(self.disconnect_error, self.parity_error, self.esc_error, self.credit_error, self.link_disabled))
        m.d.comb += last_is_ep.eq((self.tx_fifo_r_data_in == CHAR_EEP) | (self.tx_fifo_r_data_in == CHAR_EOP))
        
        with m.FSM() as recovery_fsm:
            with m.State(RecoveryState.NORMAL):
                with m.If((self.link_state == DataLinkState.RUN) & (input_error != 0)):
                    m.d.sync += self.recovery_error.eq(input_error)
                    m.next = RecoveryState.RECOVERY_DISCARD_TX

            with m.State(RecoveryState.RECOVERY_DISCARD_TX):
                with m.If(~self.tx_fifo_r_rdy_in | last_is_ep):
                    m.next = RecoveryState.RECOVERY_ADD_EEP_RX
            
            with m.State(RecoveryState.RECOVERY_ADD_EEP_RX):
                with m.If(self.rx_fifo_w_rdy_in):
                    m.next = RecoveryState.NORMAL

        # TX FIFO r_* management
        with m.If(recovery_fsm.ongoing(RecoveryState.RECOVERY_DISCARD_TX)):
            # The data char is the previously read
            with m.If(~last_is_ep & self.tx_fifo_r_rdy_in):
                m.d.comb += self.tx_fifo_r_en_out.eq(1)
            with m.Else():
                m.d.comb += self.tx_fifo_r_en_out.eq(0)

            m.d.comb += [
                self.tx_fifo_r_rdy_out.eq(0),
                self.tx_fifo_r_data_out.eq(0)
            ]
        with m.Else():
            m.d.comb += [
                self.tx_fifo_r_en_out.eq(self.tx_fifo_r_en_in),
                self.tx_fifo_r_rdy_out.eq(self.tx_fifo_r_rdy_in),
                self.tx_fifo_r_data_out.eq(self.tx_fifo_r_data_in)
            ]
        

        # RX FIFO w_* management
        with m.If(recovery_fsm.ongoing(RecoveryState.RECOVERY_ADD_EEP_RX)):
            with m.If(self.rx_fifo_w_rdy_in):
                m.d.comb += [
                    self.rx_fifo_w_data_out.eq(CHAR_EEP),
                    self.rx_fifo_w_en_out.eq(1)
                ]
            
            m.d.comb += [
                self.rx_fifo_w_rdy_out.eq(0)
            ]
        with m.Else():
            m.d.comb += [
                self.rx_fifo_w_rdy_out.eq(self.rx_fifo_w_rdy_in),
                self.rx_fifo_w_data_out.eq(self.rx_fifo_w_data_in),
                self.rx_fifo_w_en_out.eq(self.rx_fifo_w_en_in)
            ]

        return m

    def ports(self):
        return [
            self.link_state,
            self.link_disabled,
            self.disconnect_error,
            self.parity_error,
            self.esc_error,
            self.credit_error,

            self.rx_fifo_w_rdy_in,
            self.rx_fifo_w_rdy_out,
            self.rx_fifo_w_en_in,
            self.rx_fifo_w_en_out,
            self.rx_fifo_w_data_in,
            self.rx_fifo_w_data_out,

            self.tx_fifo_r_rdy_in,
            self.tx_fifo_r_rdy_out,
            self.tx_fifo_r_en_in,
            self.tx_fifo_r_en_out,
            self.tx_fifo_r_data_in,
            self.tx_fifo_r_data_out,

            self.recovery_error,
        ]
