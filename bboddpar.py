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
        return 'BBO Tourney Double Dummy Par Analysis'

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

        if False:
            # pprint(travellers)
            # for each north and east player compare our score with the other results on that same traveller
            # go thru and do comparisons for win, tie, loss
            wlt = nested_dict()
            for bdnum in range (1, self.args.boards + 1):
                nsPoints = {}
                ewPoints = {}
                pctScores = {}
                for tline in travellers[bdnum]:
                    # print(tline.__dict__)
                    for player in tline.playerDir[:2]:
                        if tline.nsPoints is not None:
                            playerIdx = tline.playerDir.index(player)
                            points = tline.nsPoints if playerIdx in [0, 2] else (-1 * tline.nsPoints)
                            pctScore = tline.nsScore if playerIdx in [0, 2] else (100 - tline.nsScore)
                            if playerIdx == 0:
                                nsPoints[player] = points
                            else:
                                ewPoints[player] = points
                            pctScores[player] = pctScore
                        if bdnum == 1:
                            wlt[player]['w'] = 0
                            wlt[player]['l'] = 0
                            wlt[player]['t'] = 0

                for pointMap in [nsPoints, ewPoints]:
                    # pprint(pointMap)
                    for playera in pointMap.keys():
                        w = l = t = 0
                        for playerb in pointMap.keys():
                            if playerb != playera:
                                if pointMap[playera] > pointMap[playerb]:
                                    w += 1
                                elif pointMap[playera] < pointMap[playerb]:
                                    l += 1
                                else:
                                    t +=1
                                # print(playera, playerb, pointMap[playera], pointMap[playerb], w, l, t)
                        # print(bdnum, playera, pctScores[playera],  w, l, t)
                        wlt[playera]['w'] += w
                        wlt[playera]['l'] += l
                        wlt[playera]['t'] += t

            pprint(wlt)

        # hand, ddtable and par display
        if True:
            for bdnum in range (1, self.args.boards + 1):
                # print(f'{bdnum:2}: {BboDDParTravLine.dealInfos[bdnum].pbnDealString}')
                BboDDParTravLine.dealInfos[bdnum].printHand()
                BboDDParTravLine.dealInfos[bdnum].printTable()
                print()




#-------- main stuff starts here -----------

BboDDParReporter().genReport()
