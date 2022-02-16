# amaranth: UnusedElaboratable=no

import unittest

from amaranth import *
from amaranth_spacewire import SpWTransmitter, WrongSignallingRate

BIT_FREQ_MIN = 2e6

class test661(unittest.TestCase):
    def test_6_6_1(self):
        dut1 = SpWTransmitter(20e6, BIT_FREQ_MIN)

        with self.assertRaises(WrongSignallingRate):
            dut2 = SpWTransmitter(20e6, BIT_FREQ_MIN - 1)
