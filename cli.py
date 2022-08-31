import argparse
import warnings
from amaranth import cli

from amaranth_spacewire import SpWNode

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("--time-master",
            default=False, action="store_true",
            help="The time master sends the time-codes whenever the tick_in input is asserted")

    parser.add_argument("--src-freq",
            default=50e6,
            help="Clock frequency")

    parser.add_argument("--user-freq",
            default=10e6,
            help="Link user frequency")

    parser.add_argument("--reset-freq",
            default=10e6,
            help="Link reset frequency")

    parser.add_argument("--rx-tokens",
            type=int, default=7,
            help="Number of RX tokens (fifo size / 8)")

    parser.add_argument("--tx-tokens",
            type=int, default=7,
            help="Number of TX tokens (fifo size / 8)")

    cli.main_parser(parser)

    args = parser.parse_args()

    spw_node = SpWNode(int(float(args.src_freq)), int(float(args.reset_freq)), int(float(args.user_freq)), time_master=args.time_master, rx_tokens=args.rx_tokens, tx_tokens=args.tx_tokens, debug=False)

    ports = spw_node.ports()

    cli.main_runner(parser, args, spw_node, name="amaranth_spacewire_node", ports=ports)


if __name__ == "__main__":
    main()
