import sys
import time
import os
from pprint import pprint

from bboparse import BboParserBase, BboTravLineBase

global args

travTableData = []
map = {}
players = {}
partners = {}
opps = {}

class BboDefOffParser(BboParserBase):
    def appDescription(self):
        return 'BBO Tourney Defense/Offense Analysis'

    def addParserArgs(self, parser):
        pass
    
class BboDefOffTravLine(BboTravLineBase):
    def __init__(self, bdnum, row):
        super(BboDefOffTravLine, self).__init__(bdnum, row)


#-------- main stuff starts here -----------
myBboParser = BboDefOffParser()
args = myBboParser.parseArguments()
if args.debug:
    print(args.__dict__)
    sys.exit(1)

travTableData = []
#read all traveler files into travTableData
travTableData = myBboParser.readAllTravFiles()

BboDefOffTravLine.importArgs(args)
for bdnum in range (1, args.boards + 1):
    # place rows in big table indexed by boardnumber and North and East names
    for row in travTableData[bdnum]:
        tline = BboDefOffTravLine(bdnum, row)
        print(bdnum, end='')
        pprint(tline.__dict__)
