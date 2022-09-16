import enum


class RecoveryState(enum.Enum):
    NORMAL = 0
    RECOVERY_DISCARD_TX = 1
    RECOVERY_ADD_EEP_RX = 2


class DataLinkState(enum.Enum):
    ERROR_RESET = 0
    ERROR_WAIT = 1
    READY = 2
    STARTED = 3
    CONNECTING = 4
    RUN = 5


class TransmitterState(enum.Enum):
    WAIT                    = 0
    WAIT_TX_START_DATA      = 1
    WAIT_TX_START_CONTROL   = 2
    SEND_NULL_A             = 4
    SEND_NULL_B             = 5
    SEND_NULL_C             = 6

