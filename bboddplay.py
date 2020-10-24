import sys
import time
import os
import collections
import sys
import time
import os
import collections
from pprint import pprint
import re
import tabulate
sys.path.append('./python-dds/examples')

import dds
import ctypes
import functions

from bbobase import BboBase
from bboddpartravline import BboDDParTravLine

def nested_dict():
    return collections.defaultdict(nested_dict)

class BboDDParReporter(BboBase):
    def appDescription(self):
        return 'BBO Tourney Double Dummy Play Analysis'

    def addParserArgs(self, parser):
        pass

    def childGenReport(self):
        BboDDParTravLine.importArgs(self.args)
        travellers = {}

        for bdnum in range (1, self.args.boards + 1):
            travellers[bdnum] = []
            for row in self.travTableData[bdnum]:
                tline = BboDDParTravLine(bdnum, row)
                # tline.getDDTable()
                travellers[bdnum].append(tline)
        # print('travTableData and travellers are set up')

        # hand, ddtable and par display
        if True:
            for bdnum in range (1, self.args.boards + 1):
                BboDDParTravLine.dealInfos[bdnum].printHand()
                for tline in travellers[bdnum]:
                    if self.args.debug:
                        print(bdnum, tline.playerDir, tline.playCount, tline.playString, tline.claimed)
                    print(f'Board {bdnum}, {tline.north} vs {tline.east}, {tline.contract} by {tline.decl}')
                    tline.getPlayAnalysis()
                    print(f'Tricks Actually Taken: {tline.tricks}')
                    print()
                print()
                


#-------- main stuff starts here -----------

BboDDParReporter().genReport()
