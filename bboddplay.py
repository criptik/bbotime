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

class BboDDPlayReporter(BboBase):
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
                tline = BboDDParTravLine(bdnum, row, self.travParser)
                tline.checkAndAppend(travellers)
        # print('travTableData and travellers are set up')

        print('<html><body><pre>')
        for bdnum in range (1, self.args.boards + 1):
            BboDDParTravLine.dealInfos[bdnum].printHand()
            for tline in travellers[bdnum]:
                if self.args.debug:
                    print(bdnum, tline.playerDir, tline.playCount, tline.playString, tline.claimed)
                print(f"Board {bdnum}, NS:{tline.coloredName('N')}-{tline.coloredName('S')} vs EW:{tline.coloredName('E')}-{tline.coloredName('W')}, {tline.contract} by {tline.decl}({tline.coloredName(tline.decl)})")
                tline.getPlayAnalysis()
                tline.formatPlayAnalysis()
                print(f'Tricks Actually Taken: {tline.tricks}')
                print()
            print()
        print('</pre></body></html>')
                


#-------- main stuff starts here -----------

BboDDPlayReporter().genReport()
