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

        self.printHTMLOpening()
        for bdnum in range (1, self.args.boards + 1):
            travellers[bdnum] = []
            for row in self.travTableData[bdnum]:
                tline = BboDDParTravLine(bdnum, row, self.travParser)
                tline.checkAndAppend(travellers)

        for bdnum in range (1, self.args.boards + 1):
            BboDDParTravLine.printHandPlusDDTable(bdnum)
            for tline in travellers[bdnum]:
                self.printPlayDetailsTable(bdnum, tline, addReplayButton=True)
            print()
        self.printHTMLClosing()

    def printPlayDetailsTable(self, bdnum, tline, addReplayButton=False):
        if self.args.debug:
            print(bdnum, tline.playerDir, tline.playCount, tline.playString, tline.claimed)
        print(tline.summaryLine())
        if tline.contract is not None:
            tline.getPlayAnalysis()
            tline.formatPlayAnalysis(addReplayButton)
            print(f'Tricks Actually Taken: {tline.tricks}')
            print()
    

#-------- main stuff starts here -----------

if __name__ == '__main__':
    BboDDPlayReporter().genReport()
