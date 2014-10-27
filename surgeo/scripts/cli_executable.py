#!/usr/local/bin/python3
#coding: utf-8
'''This is an executable wrapper for surgeo.'''

###############################################################################
# Main
###############################################################################

import sys

import surgeo

from surgeo.scripts import gui_executable


def cli_main(*args):
    '''This is the main application when running the program from a CLI.

    Args:
        --setup: (0 args) downloads and creates database for model creation
        --pipe: (0 args) takes stdin, processes, and sends to stdout
        --file: (2 args) takes 1. filepath input csv 2. filepath output csv
        --simple: (2 args) takes zip and surname, returns text string
        --complex: (2 args) takes zip and surname, returns detailed string
        -q: 'quiet' option that suppresses output.
    Returns:
        --setup: None
        --pipe: long text string
        --file: None (output to csv file)
        --simple: text string ('White')
        --complex: long text string
    Raises:
        None

    '''

##### Parse arguments
    parsed_args = surgeo.utilities.get_parser_args()
    if parsed_args.quiet:
        surgeo.redirector.direct_to_null()
##### Setup
    surgeo.redirector.add('Running setup ...')
##### Pipe
    if parsed_args.pipe:
        surgeo.redirector.direct_to_stdout()
        model = surgeo.SurgeoModel()
        try:
            while True:
                for line in sys.stdin:
                    try:
                        # Remove surrounding whitespace
                        line.strip()
                        zcta, surname = line.split()
                        result = model.race_data(zcta, surname)
                    except ValueError:
                        result = model.race_data('00000', 'BAD_NAME')
                    print(result.as_string)
        except EOFError:
            pass
##### Simple
    elif parsed_args.simple:
        model = surgeo.SurgeoModel()
        zcta = parsed_args.simple[0]
        surname = parsed_args.simple[1]
        race = model.guess_race(zcta, surname)
        print(race)
##### Complex
    elif parsed_args.complex:
        model = surgeo.SurgeoModel()
        zcta = parsed_args.complex[0]
        surname = parsed_args.complex[1]
        result = model.race_data(zcta, surname)
        print(result.as_string)
##### File
    elif parsed_args.file:
        model = surgeo.SurgeoModel()
        infile = parsed_args.file[0]
        outfile = parsed_args.file[1]
        model.process_csv(infile, outfile)
##### If no argument, GUI. Console should remain.
    elif not any([parsed_args.setup,
                  parsed_args.pipe,
                  parsed_args.simple,
                  parsed_args.complex,
                  parsed_args.file]):
        gui_executable()

if __name__ == "__main__":
    sys.exit(cli_main(sys.argv[1:]))
