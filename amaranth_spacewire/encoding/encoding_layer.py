from amaranth import *

from amaranth_spacewire.encoding.transmitter import Transmitter
from amaranth_spacewire.encoding.receiver import Receiver

class EncodingLayer(Elaboratable):
    def __init__(self, srcfreq,
                 rstfreq=Transmitter.TX_FREQ_RESET,
                 txfreq=Transmitter.TX_FREQ_RESET,
                 disconnect_delay=850e-9):

        # Signals for the Data Link layer
        # TX
        self.tx_enable = Signal()
        self.tx_char = Signal(9)
        self.send = Signal()
        self.sent_n_char = Signal()
        self.send_fct = Signal()
        self.sent_fct = Signal()
        self.sent_null = Signal()
        self.tx_ready = Signal()

        # RX
        self.rx_enable = Signal()
        self.got_fct = Signal()
        self.got_esc = Signal()
        self.got_null = Signal()
        self.got_bc = Signal()
        self.rx_char = Signal(9)
        self.got_n_char = Signal()
        self.parity_error = Signal()
        self.read_error = Signal()
        self.esc_error = Signal()
        self.disconnect_error = Signal()
        
        # Signals for the Physical Layer
        self.data_output = Signal()
        self.strobe_output = Signal()
        self.data_input = Signal()
        self.strobe_input = Signal()
        
        # Signals for the MIB
        self.tx_switch_freq = Signal()

        # Internals
        self._srcfreq = srcfreq
        self._rstfreq = rstfreq
        self._txfreq = txfreq
        self._disconnect_delay = disconnect_delay
        
    def elaborate(self, platform):
        m = Module()

        m.submodules.tx = tx = Transmitter(self._srcfreq, self._rstfreq, self._txfreq)
        m.submodules.rx = rx = Receiver(self._srcfreq, self._disconnect_delay)
        
        m.d.comb += [
            rx.data.eq(self.data_input),
            rx.strobe.eq(self.strobe_input),
            rx.enable.eq(self.rx_enable),
            
            tx.enable.eq(self.tx_enable),
            tx.switch_user_tx_freq.eq(self.tx_switch_freq),
            tx.char.eq(self.tx_char),
            tx.send.eq(self.send),
            tx.send_fct.eq(self.send_fct),

            self.got_fct.eq(rx.got_fct),
            self.got_esc.eq(rx.got_esc),
            self.got_null.eq(rx.got_null),
            self.got_bc.eq(rx.got_bc),
            self.rx_char.eq(rx.char),
            self.got_n_char.eq(rx.got_n_char),
            self.parity_error.eq(rx.parity_error),
            self.read_error.eq(rx.read_error),
            self.esc_error.eq(rx.esc_error),
            self.disconnect_error.eq(rx.disconnect_error),
            self.data_output.eq(tx.data),
            self.strobe_output.eq(tx.strobe),
            self.sent_n_char.eq(tx.sent_n_char),
            self.sent_fct.eq(tx.sent_fct),
            self.sent_null.eq(tx.sent_null),
            self.tx_ready.eq(tx.ready),
        ]

        return m
    
    def ports(self):
        return [
            self.tx_enable,
            self.tx_char,
            self.send,
            self.sent_n_char,
            self.send_fct,
            self.sent_fct,
            self.sent_null,
            self.tx_ready,
            self.rx_enable,
            self.got_fct,
            self.got_esc,
            self.got_null,
            self.got_bc,
            self.rx_char,
            self.got_n_char,
            self.parity_error,
            self.read_error,
            self.esc_error,
            self.disconnect_error,
            self.data_output,
            self.strobe_output,
            self.data_input,
            self.strobe_input,
            self.tx_switch_freq,
        ]