from amaranth import *
from amaranth.lib.fifo import SyncFIFOBuffered

from amaranth_spacewire.datalink.fsm import DataLinkFSM
from amaranth_spacewire.misc.states import DataLinkState
from amaranth_spacewire.datalink.recovery_fsm import RecoveryFSM, RecoveryState
from amaranth_spacewire.datalink.flow_control_manager import FlowControlManager
from amaranth_spacewire.misc.constants import CHAR_EEP, CHAR_EOP, CHAR_FCT, MAX_TX_CREDIT


class DataLinkLayer(Elaboratable):
    def __init__(self, srcfreq,
                       transission_delay=12.8e-6,
                       fifo_depth_tokens=7):

        # Signals for Encoding layer
        self.got_null = Signal()
        self.got_fct = Signal()
        self.got_n_char = Signal()
        self.got_bc = Signal()
        # TODO doc this error
        self.read_error = Signal()
        self.disconnect_error = Signal()
        self.parity_error = Signal()
        self.esc_error = Signal()
        self.send_fct = Signal()
        self.sent_fct = Signal()
        self.sent_n_char = Signal()
        self.sent_null = Signal()

        self.rx_enable = Signal()
        self.rx_char = Signal(9)

        # TODO: Prefix all tx with tx and all rx with rx
        self.tx_enable = Signal()
        self.tx_char = Signal(9)
        self.tx_send = Signal()
        self.tx_ready = Signal()

        # Signals for the Network layer
        # RX FIFO
        self.r_en = Signal()
        self.r_data = Signal(9)
        self.r_rdy = Signal()
        # TX FIFO
        self.w_en = Signal()
        self.w_data = Signal(9)
        self.w_rdy = Signal()

        # Signals for the MIB
        self.link_state = Signal(DataLinkState)
        self.link_error_flags = Signal(5)
        self.link_tx_credit = Signal(range(MAX_TX_CREDIT + 1))
        self.link_rx_credit = Signal(range(8 * fifo_depth_tokens + 1))

        self.link_disabled = Signal()
        self.link_start = Signal()
        self.autostart = Signal()

        # Internals
        self._srcfreq = srcfreq
        self._transission_delay = transission_delay
        self._fifo_depth_tokens = fifo_depth_tokens

    def elaborate(self, platform):
        m = Module()
        
        rx_fifo_w_rdy = Signal()
        tx_fifo_r_en = Signal()
        tx_fifo_r_rdy = Signal()
        tx_fifo_r_data = Signal(9)

        m.submodules.rx_fifo = rx_fifo = SyncFIFOBuffered(width=9, depth=8 * self._fifo_depth_tokens)
        m.submodules.tx_fifo = tx_fifo = SyncFIFOBuffered(width=9, depth=8 * self._fifo_depth_tokens)
        m.submodules.fsm = fsm = DataLinkFSM(self._srcfreq, self._transission_delay)
        m.submodules.rec_fsm = rec_fsm = RecoveryFSM()
        m.submodules.flow_control_manager = fcm = FlowControlManager(fifo_depth_tokens=self._fifo_depth_tokens)

        m.d.comb += [
            #######################################################
            # Data Link FSM
            #######################################################
            fsm.got_fct.eq(self.got_fct),
            fsm.sent_fct.eq(self.sent_fct),
            fsm.got_n_char.eq(self.got_n_char),
            fsm.got_null.eq(self.got_null),
            fsm.sent_null.eq(self.sent_null),
            fsm.got_bc.eq(self.got_bc),
            fsm.read_error.eq(self.read_error),
            fsm.credit_error.eq(fcm.credit_error),
            fsm.disconnect_error.eq(self.disconnect_error),
            fsm.parity_error.eq(self.parity_error),
            fsm.esc_error.eq(self.esc_error),
            fsm.link_disabled.eq(self.link_disabled),
            fsm.link_start.eq(self.link_start),
            fsm.autostart.eq(self.autostart),
            fsm.recovery_state.eq(rec_fsm.recovery_state),
            
            #######################################################
            # Recovery FSM
            #######################################################
            rec_fsm.link_state.eq(fsm.link_state),
            rec_fsm.link_disabled.eq(self.link_disabled),
            rec_fsm.disconnect_error.eq(self.disconnect_error),
            rec_fsm.parity_error.eq(self.parity_error),
            rec_fsm.esc_error.eq(self.esc_error),
            rec_fsm.credit_error.eq(fcm.credit_error),

            rec_fsm.rx_fifo_w_rdy_in.eq(rx_fifo.w_rdy),
            rx_fifo_w_rdy.eq(rec_fsm.rx_fifo_w_rdy_out),

            rec_fsm.rx_fifo_w_en_in.eq(self.got_n_char),
            rx_fifo.w_en.eq(rec_fsm.rx_fifo_w_en_out),

            rec_fsm.rx_fifo_w_data_in.eq(self.rx_char),
            rx_fifo.w_data.eq(rec_fsm.rx_fifo_w_data_out),

            rec_fsm.tx_fifo_r_rdy_in.eq(tx_fifo.r_rdy),
            tx_fifo_r_rdy.eq(rec_fsm.tx_fifo_r_rdy_out),

            rec_fsm.tx_fifo_r_en_in.eq(tx_fifo_r_en),
            tx_fifo.r_en.eq(rec_fsm.tx_fifo_r_en_out),

            rec_fsm.tx_fifo_r_data_in.eq(tx_fifo.r_data),
            tx_fifo_r_data.eq(rec_fsm.tx_fifo_r_data_out),

            rec_fsm.tx_fifo_w_rdy_in.eq(tx_fifo.w_rdy),
            self.w_rdy.eq(rec_fsm.tx_fifo_w_rdy_out),

            rec_fsm.tx_fifo_w_en_in.eq(self.w_en),
            tx_fifo.w_en.eq(rec_fsm.tx_fifo_w_en_out),

            #######################################################
            # Flow Control Manager
            #######################################################
            self.send_fct.eq(fcm.send_fct),
            fcm.got_fct.eq(self.got_fct),
            fcm.sent_fct.eq(self.sent_fct),
            fcm.got_n_char.eq(self.got_n_char),
            fcm.sent_n_char.eq(self.sent_n_char),
            fcm.link_state.eq(fsm.link_state),
            self.link_tx_credit.eq(fcm.tx_credit),
            self.link_rx_credit.eq(fcm.rx_credit),
            fcm.tx_ready.eq(self.tx_ready),
            fcm.rx_fifo_level.eq(rx_fifo.level),

            #######################################################
            # FIFOs
            #######################################################
            rx_fifo.r_en.eq(self.r_en),
            self.r_rdy.eq(rx_fifo.r_rdy),
            self.r_data.eq(rx_fifo.r_data),

            tx_fifo.w_data.eq(self.w_data),

            #######################################################
            # 
            #######################################################
            self.link_state.eq(fsm.link_state),
            self.link_error_flags.eq(rec_fsm.recovery_error),
            self.tx_char.eq(tx_fifo_r_data),
        ]
        
        with m.If(~self.send_fct & self.tx_ready & fcm.tx_credit.any()):
            m.d.comb += [
                self.tx_send.eq(tx_fifo_r_rdy),
                tx_fifo_r_en.eq(tx_fifo_r_rdy)
            ]
        with m.Else():
            m.d.comb += [
                self.tx_send.eq(0),
                tx_fifo_r_en.eq(0)
            ]
        
        with m.If(fsm.link_state == DataLinkState.ERROR_RESET):
            m.d.comb += self.rx_enable.eq(0)
        with m.Else():
            m.d.comb += self.rx_enable.eq(1)

        with m.If((fsm.link_state == DataLinkState.STARTED)
                  | (fsm.link_state == DataLinkState.CONNECTING)
                  | (fsm.link_state == DataLinkState.RUN)):
            m.d.comb += self.tx_enable.eq(1)
        with m.Else():
            m.d.comb += self.tx_enable.eq(0)
        
        return m

    def ports(self):
        return [
            self.got_null,
            self.got_fct,
            self.got_n_char,
            self.got_bc,
            self.receive_error,
            self.disconnect_error,
            self.parity_error,
            self.esc_error,
            self.send_fct,
            self.sent_fct,
            self.sent_n_char,
            self.sent_null,
            self.rx_enable,
            self.rx_char,
            self.tx_enable,
            self.tx_char,
            self.tx_ready,
            self.r_en,
            self.r_data,
            self.r_rdy,
            self.w_en,
            self.w_data,
            self.w_rdy,
            self.link_state,
            self.link_error_flags,
            self.link_tx_credit,
            self.link_rx_credit,
            self.link_disabled,
            self.link_start,
            self.autostart,
        ]
