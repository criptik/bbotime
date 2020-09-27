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

from bboparse import BboParserBase, BboTravLineBase

global args

travTableData = []

class BboDDParParser(BboParserBase):
    def appDescription(self):
        return 'BBO Tourney Double Dummy Par Analysis'

    def addParserArgs(self, parser):
        pass

def cardRank(c):
    return '23456789TJQKA'.index(c)




class BboDDParTravLine(BboTravLineBase):
    # class data of DealInfo objects keyed by bdnum
    dealInfos = {}

    def __init__(self, bdnum, row):
        super(BboDDParTravLine, self).__init__(bdnum, row)
        # convert the captured LIN string into a pbn deal specification
        if BboDDParTravLine.dealInfos.get(bdnum) is None:
            BboDDParTravLine.dealInfos[bdnum] = self.DealInfo(self.bdnum, self.linToPbnDeal())
        
    def linToPbnDeal(self):
        s = self.linStr
        # subsitute % symbols
        s = re.sub('%7C', '|', s)
        s = re.sub('%2C', ' ', s)
        # print(s)
        # get rid of everything up to deal info
        s = re.sub('^.*md\|\d', '', s)
        # and everythin after
        s = re.sub('\|rh\|.*$', '', s)
        # replace suits with separators
        s = re.sub('S', ' ', s)
        s = re.sub('[HDC]', '.', s)
        s = s.lstrip(' ')
        s = s.rstrip(' ')
        str3Hands = s.split('  ')
        # print(str3Hands)

        # build hands structure to create Deal
        # the created Deal will fill in the missing 4th hand
        hands = []
        for handstr in str3Hands:
            hands.append(self.Deal.Hand.fromPbnHandStr(handstr))
        mydeal = self.Deal(hands)

        pbnDealString = mydeal.toPbnString()
        # print('dealpbn= ', pbnDealString)
        return pbnDealString

    def getDDTable(self):
        dealInfo = BboDDParTravLine.dealInfos[self.bdnum]
        return dealInfo.getDDTable()
            
    # inner class DealInfo
    class DealInfo(object):
        SuitSyms = {
                'S' : '\N{BLACK SPADE SUIT}',
                'H' : '\N{WHITE HEART SUIT}',
                'D' : '\N{WHITE DIAMOND SUIT}',
                'C' : '\N{BLACK CLUB SUIT}',
            }
        Testing = True
        
        def __init__(self, bdnum, pbnDealString):
            self.bdnum = bdnum
            self.DDdealsPBN = dds.ddTableDealsPBN()
            self.DDdealsPBN.noOfTables = 1
            self.DDdealsPBN.deals[0].cards = pbnDealString.encode('utf-8')
            self.pbnDealString = pbnDealString  #saved in case we need it later

            # other fields left for later computation
            self.ddTable = None
            self.parResults = None
            
        def getDDTable(self):
            if self.ddTable is None:
                # print(f'...computing DD Table for bdnum {bdnum}')
                self.computeDDTable()
            return self.ddTable
        
        def computeDDTable(self):
            if self.Testing:
                return
            self.ddTable = dds.ddTablesRes()
            self.pres = dds.allParResults()

            mode = 0
            tFilter = ctypes.c_int * dds.DDS_STRAINS
            trumpFilter = tFilter(0, 0, 0, 0, 0)
            line = ctypes.create_string_buffer(80)

            dds.SetMaxThreads(0)

            res = dds.CalcAllTablesPBN(ctypes.pointer(self.DDdealsPBN), mode, trumpFilter, ctypes.pointer(self.ddTable), ctypes.pointer(self.pres))


        def printHand(self):
            if False:
                functions.PrintPBNHand(f'Board {self.bdnum}', self.DDdealsPBN.deals[0].cards)
            else:
                handStr = functions.getHandStringPBN(f'Board {self.bdnum}', self.DDdealsPBN.deals[0].cards)
                for suit in self.SuitSyms.keys():
                    handStr = re.sub(f'{suit} ', f'{self.SuitSyms[suit]} ', handStr)
                print(handStr)

        def getDDTricks(self, suit, dir):
            suitidx = 'SHDCNT'.index(suit)
            diridx = 'NESW'.index(dir)
            if self.Testing:
                return ((suitidx + diridx) % 4) + 5
            table = ctypes.pointer(self.ddTable.results[0])
            return table.contents.resTable[suitidx][diridx]
            
        def printTable(self):
            # self.getDDTable()
            print(f'DD Table for Board {self.bdnum}:\n---------------------')
            print(f'    ', end='')
            suits = ['C', 'D', 'H', 'S', 'NT']
            for suit in suits:
                if True and suit != 'NT':
                    print(f'{self.SuitSyms[suit]:>4}', end='')
                else:
                    print(f'{suit:>4}', end='')
            print()
            for dir in 'NSEW':
                print(f'{dir:>4}', end='')
                for suit in suits:
                    numTricks = self.getDDTricks(suit, dir)
                    trickStr = '--' if numTricks <= 6 else f'{numTricks - 6}'
                    print(f'{trickStr : >4}', end='')
                print()
            print()
            
        def printTableClassic(self):
            self.getDDTable()
            print('Table Classic\n-------')
            functions.PrintTable(ctypes.pointer(self.ddTable.results[0]))

        def getPar(self):
            self.getDDTable()
            if self.parResults is None:
                self.computePar()

        def computePar(self):
            self.getDDTable()
            self.parResults = dds.parResultsDealer()
            dlr = (self.bdnum-1) % 4
            vul = [0,2,3,1,2,3,1,0,3,1,0,2,1,0,2,3][(self.bdnum-1) % 16]
            res = dds.DealerPar(ctypes.pointer(self.ddTable.results[0]), ctypes.pointer(self.parResults), dlr, vul)
            return self.parResults
        
        def printPar(self):
            print(f'Par for board {bdnum}: ', end='')
            self.computePar()
            pcontents = ctypes.pointer(self.parResults).contents
            print(f'NS {pcontents.score:+}', end='')
            for i in range(pcontents.number):
                print(f', {pcontents.contracts[i].value.decode("utf-8")}', end='')
            print()
            
        def printParClassic(self):
            print(f'Par for board {bdnum}')
            self.computePar()
            functions.PrintDealerPar(ctypes.pointer(self.parResults))    
            
    # inner class Deal
    class Deal(object):
        # a set of 4 hands
        def __init__(self, hands):
            self.hands = hands
            if len(hands) == 3:
                # fill in missing hand
                missHand = self.Hand.allCards()

                for hand in self.hands:
                    for (i, suitset) in enumerate(hand.suits):
                        missHand.suits[i] = missHand.suits[i] - suitset

                self.hands.append(missHand)



        def toPbnString(self):
            result = 'S:'  # BBO deals always start with 'S'
            for (i, hand) in enumerate(self.hands):
                if i != 0:
                    result = result + ' '
                result = result + hand.toPbnString()
            return result

        # inner class Deal.Hand
        class Hand(object):
            def __init__(self):
                self.suits = []

            @classmethod
            def fromPbnHandStr(cls, handstr):
                newHand = cls()
                for suitstr in handstr.split('.'):
                    newHand.suits.append(set(suitstr))
                return newHand

            @classmethod
            def fromSuitSets(cls, suitsets):
                newHand = cls()
                for suitset in suitsets:
                    newHand.suits.append(suitset)
                return newHand

            @classmethod
            def allCards(cls):
                newHand = cls()
                for n in range(4):
                    newHand.suits.append(set('23456789TJQKA'))
                return newHand

            def toPbnString(self):
                result = ''
                for (n, suit) in enumerate(self.suits):
                    if n != 0:
                        result = result + '.'
                    result = result + ''.join(sorted(suit, reverse=True, key=cardRank))
                return result

            def __str__(self):
                result = ''
                for s in self.suits:
                    result = result + f'{s} '
                return result

        

def nested_dict():
    return collections.defaultdict(nested_dict)

#-------- main stuff starts here -----------

myBboParser = BboDDParParser()
args = myBboParser.parseArguments()
if args.debug:
    print(args.__dict__)

travTableData = []

#read all traveler files into travTableData
travTableData = myBboParser.readAllTravFiles()
BboDDParTravLine.importArgs(args)
travellers = {}
if False:
    #temporary for testing
    args.boards = 1 

for bdnum in range (1, args.boards + 1):
    travellers[bdnum] = []
    for row in travTableData[bdnum]:
        tline = BboDDParTravLine(bdnum, row)
        # tline.getDDTable()
        travellers[bdnum].append(tline)
print('travTableData and travellers are set up')

if False:
    # pprint(travellers)
    # for each north and east player compare our score with the other results on that same traveller
    # go thru and do comparisons for win, tie, loss
    wlt = nested_dict()
    for bdnum in range (1, args.boards + 1):
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
    for bdnum in range (1, args.boards + 1):
        # print(f'{bdnum:2}: {BboDDParTravLine.dealInfos[bdnum].pbnDealString}')
        BboDDParTravLine.dealInfos[bdnum].printHand()
        # BboDDParTravLine.dealInfos[bdnum].printTableClassic()
        BboDDParTravLine.dealInfos[bdnum].printTable()
        if not BboDDParTravLine.DealInfo.Testing:
            BboDDParTravLine.dealInfos[bdnum].printPar()
    
