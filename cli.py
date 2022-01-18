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
            type=int, default=50,
            help="Clock frequency [MHz]")

    parser.add_argument("--link-freq",
            type=int, default=10,
            help="Link frequency [MHz]")

    cli.main_parser(parser)

    args = parser.parse_args()

    spw_node = SpWNode(args.src_freq * 1e6, args.link_freq * 1e6, time_master=args.time_master, debug=False)

    ports = spw_node.ports()

    cli.main_runner(parser, args, spw_node, name="amaranth_spacewire_node", ports=ports)


if __name__ == "__main__":
    main()
