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

class BboBlameReporter(BboBase):
    def appDescription(self):
        return 'BBO Tourney Blame Analysis'

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

        numplayers = len(wlt.keys())
        numrows = numplayers
        numcols = 4

        ary = [['' for i in range(numcols)] for j in range(numrows)]
        headers = ['Name', 'W', 'T', 'L']
        for (ridx, player) in enumerate(sorted(wlt.keys(), reverse=True, key=lambda player: wlt[player]['w'])):
            ary[ridx] = [player]
            for col in ['w', 't', 'l']:
                ary[ridx].append(wlt[player][col])
            
        print(tabulate.tabulate(ary, headers, tablefmt='simple'), end='\n\n')
        

#-------- main stuff starts here -----------

BboBlameReporter().genReport()
