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
        parser.add_argument('--bdebug', default=False, action='store_true', help='print some blame debug info') 
        pass

    def childGenReport(self):
        BboDDParTravLine.importArgs(self.args)
        travellers = {}

        # process the rows into travline objects
        for bdnum in range (1, self.args.boards + 1):
            travellers[bdnum] = []
            for row in self.travTableData[bdnum]:
                tline = BboDDParTravLine(bdnum, row)
                # tline.getDDTable()
                travellers[bdnum].append(tline)
        # print('travTableData and travellers are set up')

        # for each north and east player compare our score with the other results on that same traveller
        # go thru and do comparisons for win, tie, loss
        wlt = nested_dict()
        class WLTCounter:
            def __init__(self):
                self.W = self.L = self.T = self.Blame = 0

        class PointMap:
            def __init__(self, bdnum, dir):
                self.bdnum = bdnum
                self.dir = dir
                self.points = {}
                self.opps = {}
      
        for bdnum in range (1, self.args.boards + 1):
            pointMaps = {'NS' : PointMap(bdnum, 'NS'),
                         'EW' : PointMap(bdnum, 'EW')}
            pctScores = {}
            for tline in travellers[bdnum]:
                # print(tline.__dict__)
                for player in tline.playerDir[:2]:
                    if bdnum == 1:
                        wlt[player] = WLTCounter()
                    if tline.nsPoints is not None:
                        playerIdx = tline.playerDir.index(player)
                        points = tline.nsPoints if playerIdx in [0, 2] else (-1 * tline.nsPoints)
                        pctScore = tline.nsScore if playerIdx in [0, 2] else (100 - tline.nsScore)
                        if playerIdx == 0:
                            pointMaps['NS'].points[player] = points
                            pointMaps['NS'].opps[player] = tline.playerDir[1]
                        else:
                            pointMaps['EW'].points[player] = points
                            pointMaps['EW'].opps[player] = tline.playerDir[0]
                        pctScores[player] = pctScore
            for dir in ['NS', 'EW']:
                maxval = max(pointMaps[dir].points.values())
                nsPar = BboDDParTravLine.dealInfos[bdnum].getNSPar()
                origPar = nsPar if dir == 'NS' else -1 * nsPar
                pointMaps[dir].origPar = origPar
                pointMaps[dir].adjPar = adjPar = min(maxval, origPar)
                print(f'bd {bdnum}-{dir}:  {pointMaps[dir].points.values()}, origPar={origPar}, adjPar={adjPar}')

            # blame stuff only need be done starting with NS (starting with EW will produce same blame)
            for dir in ['NS']:
                for playera in pointMaps[dir].points.keys():
                    for playerb in pointMaps[dir].points.keys():
                        if playerb != playera:
                            apoints = pointMaps[dir].points[playera]
                            bpoints = pointMaps[dir].points[playerb]
                            matea = pointMaps[dir].opps[playerb]
                            if apoints > bpoints:
                                wlt[playera].W += 1
                                wlt[matea].W += 1
                            elif apoints < bpoints:
                                wlt[playera].L += 1
                                wlt[matea].L += 1
                                self.doLossComparison(playera, playerb, pointMaps, dir, wlt)
                            else:
                                wlt[playera].T += 1
                                wlt[matea].T += 1
                                # self.doTieComparison(playera, playerb, pointMaps[dir])

        numplayers = len(wlt.keys())
        numrows = numplayers
        headers = ['Name', 'W', 'L', 'T', 'Pct', 'Blame', 'BlamePct']
        numcols = len(headers)

        # fill in Pct, BlamePct
        for p in wlt.keys():
            wlt[p].BlamePct = 0 if wlt[p].L == 0 else 100*wlt[p].Blame / wlt[p].L
            wlt[p].Pct = 100 * (wlt[p].W + 0.5 * wlt[p].T) / (wlt[p].W + wlt[p].L + wlt[p].T)
        ary = [['' for i in range(numcols)] for j in range(numrows)]
        for (ridx, player) in enumerate(sorted(wlt.keys(), reverse=True, key=lambda player: wlt[player].Pct)):
            ary[ridx] = [player]
            for kind in headers[1:]:  # adds in wins, ties, losses, etc.
                if kind in ['BlamePct', 'Pct']:
                    ary[ridx].append(f'{wlt[player].__dict__[kind]:.2f}%')
                else:
                    ary[ridx].append(wlt[player].__dict__[kind])
                
        print(tabulate.tabulate(ary, headers, tablefmt='simple'), end='\n\n')

    def doLossComparison(self, playera, playerb, pointMaps, dir, wlt):
        pointMap = pointMaps[dir]
        otherdir = 'EW' if dir == 'NS' else 'NS'
        pointMapMate = pointMaps[otherdir]
        apoints = pointMap.points[playera]
        bpoints = pointMap.points[playerb]
        matea = pointMap.opps[playerb]
        mateb = pointMap.opps[playera]
        mateaPoints = pointMapMate.points[matea]
        if self.args.bdebug:
            print(f'Loss on {pointMap.bdnum} {dir}: {playera}={apoints} lost to {playerb}={bpoints}, adjPar-{dir}={pointMap.adjPar}, adjPar-{otherdir}={pointMapMate.adjPar}, teammate {matea}')
            print(f'        {pointMap.bdnum} blame: ', end='')
            if apoints < pointMap.adjPar:
                print(f' {dir} {playera}={apoints} did not reach adjPar={pointMap.adjPar}  ', end='')
            if mateaPoints < pointMapMate.adjPar:
                print(f', {otherdir} {matea}={mateaPoints} did not reach adjPar={pointMapMate.adjPar}  ', end='')
            print()
        blames=[]
        if apoints < pointMap.adjPar:
            blames.append(playera)
        if mateaPoints < pointMapMate.adjPar:
            blames.append(matea)
        print(blames)
        numblames = len(blames)
        for p in blames:
            wlt[p].Blame += float(1/numblames)
        
    def doTieComparison(self, playera, playerb, pointMap):
        if False:
            apoints = pointMap.points[playera]
            bpoints = pointMap.points[playerb]
            print(f'Tie on {pointMap.bdnum} {pointMap.dir}: {playera}={apoints}, {playerb}={bpoints}')

#-------- main stuff starts here -----------

BboBlameReporter().genReport()
