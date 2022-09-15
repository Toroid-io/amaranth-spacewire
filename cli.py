import argparse
import warnings
from amaranth import cli

from amaranth_spacewire import Node

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("--time-master",
            default=False, action="store_true",
            help="The time master sends the time-codes whenever the tick_in input is asserted")

    parser.add_argument("--src-freq",
            default=50e6,
            help="Clock frequency")

    parser.add_argument("--tx-freq",
            default=10e6,
            help="Link transmit frequency")

    parser.add_argument("--reset-freq",
            default=10e6,
            help="Link reset frequency")

    cli.main_parser(parser)

    args = parser.parse_args()

    spw_node = Node(int(float(args.src_freq)), int(float(args.reset_freq)), int(float(args.tx_freq)))

    ports = spw_node.ports()

    cli.main_runner(parser, args, spw_node, name="amaranth_spacewire_node", ports=ports)


if __name__ == "__main__":
    main()
