from amaranth import *
from amaranth_spacewire.encoding.encoding_layer import EncodingLayer
from amaranth_spacewire.encoding.transmitter import Transmitter
from amaranth_spacewire.datalink.datalink_layer import DataLinkLayer, DataLinkState


class Node(Elaboratable):
    def __init__(self, srcfreq, rstfreq=Transmitter.TX_FREQ_RESET, txfreq=Transmitter.TX_FREQ_RESET, transission_delay=12.8e-6, disconnect_delay=850e-9):
        # Data/Strobe
        self.data_input = Signal()
        self.strobe_input = Signal()
        self.data_output = Signal()
        self.strobe_output = Signal()

        # FIFO
        self.r_en = Signal()
        self.r_data = Signal(9)
        self.r_rdy = Signal()
        self.w_en = Signal()
        self.w_data = Signal(9)
        self.w_rdy = Signal()

        # Status signals
        self.link_state = Signal(DataLinkState)
        self.link_error_flags = Signal(5)
        self.link_tx_credit = Signal(range(56 + 1))
        self.link_rx_credit = Signal(range(56 + 1))

        # Control signals
        self.tx_switch_freq = Signal()
        self.link_disabled = Signal()
        self.link_start = Signal()
        self.autostart = Signal()

        self._srcfreq = srcfreq
        self._txfreq = txfreq
        self._rstfreq = rstfreq
        self._transission_delay = transission_delay
        self._disconnect_delay = disconnect_delay

    def elaborate(self, platform):
        m = Module()

        m.submodules.encoding_layer = encoding_layer = EncodingLayer(self._srcfreq, self._rstfreq, self._txfreq, self._disconnect_delay)
        m.submodules.datalink_layer = datalink_layer = DataLinkLayer(self._srcfreq, self._transission_delay)

        m.d.comb += [
            encoding_layer.tx_enable.eq(datalink_layer.tx_enable),
            encoding_layer.tx_char.eq(datalink_layer.tx_char),
            encoding_layer.send.eq(datalink_layer.tx_send),
            encoding_layer.send_fct.eq(datalink_layer.send_fct),
            encoding_layer.rx_enable.eq(datalink_layer.rx_enable),
            encoding_layer.data_input.eq(self.data_input),
            encoding_layer.strobe_input.eq(self.strobe_input),
            encoding_layer.tx_switch_freq.eq(self.tx_switch_freq),

            datalink_layer.r_en.eq(self.r_en),
            datalink_layer.got_null.eq(encoding_layer.got_null),
            datalink_layer.got_fct.eq(encoding_layer.got_fct),
            datalink_layer.got_bc.eq(encoding_layer.got_bc),
            datalink_layer.rx_char.eq(encoding_layer.rx_char),
            datalink_layer.got_n_char.eq(encoding_layer.got_n_char),
            datalink_layer.read_error.eq(encoding_layer.read_error),
            datalink_layer.disconnect_error.eq(encoding_layer.disconnect_error),
            datalink_layer.parity_error.eq(encoding_layer.parity_error),
            datalink_layer.esc_error.eq(encoding_layer.esc_error),
            datalink_layer.link_disabled.eq(self.link_disabled),
            datalink_layer.link_start.eq(self.link_start),
            datalink_layer.autostart.eq(self.autostart),
            datalink_layer.sent_n_char.eq(encoding_layer.sent_n_char),
            datalink_layer.sent_fct.eq(encoding_layer.sent_fct),
            datalink_layer.sent_null.eq(encoding_layer.sent_null),
            datalink_layer.tx_ready.eq(encoding_layer.tx_ready),
            datalink_layer.w_en.eq(self.w_en),
            datalink_layer.w_data.eq(self.w_data),

            self.w_rdy.eq(datalink_layer.w_rdy),
            self.link_state.eq(datalink_layer.link_state),
            self.link_error_flags.eq(datalink_layer.link_error_flags),
            self.link_tx_credit.eq(datalink_layer.link_tx_credit),
            self.link_rx_credit.eq(datalink_layer.link_rx_credit),
            self.data_output.eq(encoding_layer.data_output),
            self.strobe_output.eq(encoding_layer.strobe_output),
            self.r_data.eq(datalink_layer.r_data),
            self.r_rdy.eq(datalink_layer.r_rdy),
        ]

        return m

    def ports(self):
        return [
            self.data_input,
            self.strobe_input,
            self.data_output,
            self.strobe_output,
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
            self.tx_switch_freq,
            self.link_disabled,
            self.link_start,
            self.autostart,
        ]
