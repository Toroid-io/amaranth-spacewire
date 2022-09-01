# amaranth: UnusedElaboratable=no

import unittest

from amaranth import *
from amaranth_spacewire import SpWTransmitter, WrongSignallingRate

BIT_FREQ_MIN = 2e6

class Test(unittest.TestCase):
    def test_5_4_10_2_a(self):
        dut1 = SpWTransmitter(20e6, 10e6, BIT_FREQ_MIN)

        with self.assertRaises(WrongSignallingRate):
            dut2 = SpWTransmitter(20e6, 10e6, BIT_FREQ_MIN - 1)


if __name__ == "__main__":
    unittest.main()