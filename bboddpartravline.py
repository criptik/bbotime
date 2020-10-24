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

from bbobase import BboBase, BboTravLineBase


class BboDDParTravLine(BboTravLineBase):
    # class data of DealInfo objects keyed by bdnum
    dealInfos = {}

    def __init__(self, bdnum, row):
        super(BboDDParTravLine, self).__init__(bdnum, row)
        # convert the captured LIN string into a pbn deal specification
        if BboDDParTravLine.dealInfos.get(bdnum) is None:
            BboDDParTravLine.dealInfos[bdnum] = self.DealInfo(self.bdnum, self.linToPbnDeal())
        (self.playString, self.claimed) = self.linToPbnPlayString()
        self.playCount = int(len(self.playString)/2)
        
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
        return mydeal
    
    def linToPbnPlayString(self):
        s = self.linStr
        # subsitute % symbols
        s = re.sub('%7C', '|', s)
        s = re.sub('%2C', ' ', s)
        # get rid of everything up to play info
        s = re.sub('^.*?pc\|', '|pc|', s)
        # and everything after
        s = re.sub("\|'\);this.*$", '', s)
        # strip down to only the cards played (get rid of |pc|)
        s = re.sub('\|pc\|', '', s)
        # string returned could have claim info at end, if so break that out
        splits = re.split('\|mc\|', s)
        if len(splits) == 1:
            splits.append(None)   # no claim info
        else:
            splits[1] = int(splits[1])  # amount claimed
        return splits
        
    def getDDTable(self):
        dealInfo = BboDDParTravLine.dealInfos[self.bdnum]
        return dealInfo.getDDTable()

    def getTrumpIndex(self):
        return 'SHDCN'.index(self.trumpstr)

    def getLeaderIndex(self):
        # the hand leading to the first trick
        # where N=0, E=1, S=2, W=3
        declIdx = 'NESW'.index(self.decl)
        return (declIdx + 1) % 4

    def buildDealPBN(self, dlPBN):
        dlPBN.trump = self.getTrumpIndex()
        # dlPBN.first is the index of the hand leading to the first trick
        # where N=0, E=1, S=2, W=3
        dlPBN.first = self.getLeaderIndex()
        dealInfo = BboDDParTravLine.dealInfos[self.bdnum]
        for n in range(3):
            dlPBN.currentTrickSuit[n] = dlPBN.currentTrickRank[n] = 0
        dlPBN.remainCards = dealInfo.pbnDealString.encode('utf-8')
        
    def getPlayAnalysis(self):
        if self.decl is None:
            return
        dlPBN = dds.dealPBN()
        DDplayPBN = dds.playTracePBN()
        solved = dds.solvedPlay()
        # fill in dlPBN fields
        self.buildDealPBN(dlPBN)
        # print(dlPBN.trump,  dlPBN.first, dlPBN.remainCards)
        DDplayPBN.number = self.playCount
        DDplayPBN.cards = self.playString.encode('utf=8')
        # print(DDplayPBN.number, DDplayPBN.cards)
        threadIndex = 0
        res = dds.AnalysePlayPBN(
            dlPBN,
            DDplayPBN,
            ctypes.pointer(solved),
            threadIndex)

        # functions.PrintPBNPlay(ctypes.pointer(DDplayPBN), ctypes.pointer(solved))
        psolved = ctypes.pointer(solved)
        pplayp = ctypes.pointer(DDplayPBN)
        print(f'DD Expected Tricks: {psolved.contents.tricks[0]}')
        for i in range(1, psolved.contents.number):
            sep = '|' if i % 4 == 0 else ' '
            print(f'{chr(pplayp.contents.cards[2 * (i - 1)])}{chr(pplayp.contents.cards[2 * i - 1])}{sep}', end='')
        print()
        lasttrix = -1
        for i in range(1, psolved.contents.number):
            trix = psolved.contents.tricks[i]
            trixStr = '  ' if trix == lasttrix else f'{trix:2}'
            print(f'{trixStr} ', end='')
            lasttrix = trix
        print()
        
        # sys.exit(1)
        # DDPlayPBN 

    def getOptimumLeads(self):
        dlPBN = dds.dealPBN()
        fut2 = dds.futureTricks()
        threadIndex = 0
        line = ctypes.create_string_buffer(80)
        dds.SetMaxThreads(0)
        # fill in dlPBN fields
        self.buildDealPBN(dlPBN)
        target = -1
        solutions = 2
        mode = 0
        res = dds.SolveBoardPBN(
            dlPBN,
            target,
            solutions,
            mode,
            ctypes.pointer(fut2),
            0)
        
        if res != dds.RETURN_NO_FAULT:
            dds.ErrorMessage(res, line)
            print("DDS error {}".format(line.value.decode("utf-8")))

        if False:
            line = f'{self.bdnum}: Optimum Leads against {self.contract} by {self.decl}'
            functions.PrintFut(line, ctypes.pointer(fut2))

        return fut2
    
    # inner class DealInfo
    class DealInfo(object):
        Testing = False

        def __init__(self, bdnum, pbnDeal):
            pbnDealString = pbnDeal.toPbnString()
            # print('dealpbn= ', pbnDealString)
            self.bdnum = bdnum
            self.DDdealsPBN = dds.ddTableDealsPBN()
            self.DDdealsPBN.noOfTables = 1
            
            self.DDdealsPBN.deals[0].cards = pbnDealString.encode('utf-8')
            self.pbnDealString = pbnDealString  #saved in case we need it later
            self.pbnDeal = pbnDeal
            
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
                functions.PrintPBNHand(f'Board: {self.bdnum}', self.DDdealsPBN.deals[0].cards)
            else:
                title = f'Board:{self.bdnum}    Vul:{self.getVulStr()}   Dlr:{self.getDealerStr()}'
                # call helper function with no title
                handStr = functions.getHandStringPBN(None, self.DDdealsPBN.deals[0].cards)
                handStr = BboBase.subSuitSym(handStr)
                print(title)
                print(handStr)

        def getDDTricks(self, suit, dir):
            suitidx = 'SHDCNT'.index(suit)
            diridx = 'NESW'.index(dir)
            if self.Testing:
                return ((suitidx + diridx) % 4) + 5
            table = ctypes.pointer(self.ddTable.results[0])
            return table.contents.resTable[suitidx][diridx]
            
        def printTable(self):
            if not self.Testing:
                self.getDDTable()
            # print(f'DD Table:\n---------')
            # create list of lists for tabulate
            suits = ['C', 'D', 'H', 'S', 'NT']
            dirs = ['N', 'S', 'E', 'W']
            rows = 1 + len(dirs)
            cols = 3 + len(suits)
            tabList = [['' for i in range(cols)] for j in range(rows)]             
            # first is header row of suit names
            for (sidx, suit) in enumerate(suits):
                tabList[0][1 + sidx] = BboBase.subSuitSym(suit)
            # then one row for each direction
            for (didx, dir) in enumerate(dirs):
                tabList[1+didx][0] = dir
                for (sidx, suit) in enumerate(suits):
                    numTricks = self.getDDTricks(suit, dir)
                    trickStr = '-' if numTricks <= 6 else f'{numTricks - 6}'
                    tabList[1+didx][1+sidx] = trickStr
            # add some par info at far right
            for r in range(rows):
                tabList[r][cols-2] = ' ' * 12
            tabList[0][cols-1] = 'Par:'
            if not self.Testing:
                tabList[1][cols-1] = self.parString()
            print(tabulate.tabulate(tabList, tablefmt='plain'), end='\n\n')
            
        def printTableClassic(self):
            self.getDDTable()
            print('Table Classic\n-------')
            functions.PrintTable(ctypes.pointer(self.ddTable.results[0]))

        def getDealerIndex(self):
            return (self.bdnum-1) % 4
            
        def getDealerStr(self):
            return 'NESW'[self.getDealerIndex()]
            
        def getVulIndex(self):
            return [0,2,3,1,2,3,1,0,3,1,0,2,1,0,2,3][(self.bdnum-1) % 16]
        
        def getVulStr(self):
            strmap = {
                0 : 'None',
                1 : 'Both',
                2 : 'N/S',
                3 : 'E/W',
            }
            return strmap[self.getVulIndex()]
        
        def getNSPar(self):
            self.getDDTable()
            if self.parResults is None:
                self.computePar()
            pcontents = ctypes.pointer(self.parResults).contents
            return int(pcontents.score)
        
        def computePar(self):
            self.getDDTable()
            self.parResults = dds.parResultsDealer()
            res = dds.DealerPar(ctypes.pointer(self.ddTable.results[0]), ctypes.pointer(self.parResults), self.getDealerIndex(), self.getVulIndex())
            return self.parResults
        
        def printPar(self):
            print(f'Par for board {bdnum}: ', end='')
            print(self.parString())
            print('\n')

        def parString(self):
            self.computePar()
            pcontents = ctypes.pointer(self.parResults).contents
            txt = f'NS {pcontents.score:+}'
            for i in range(pcontents.number):
                contract = pcontents.contracts[i].value.decode("utf-8")
                cparts = contract.split('-')
                # only the first part contains a suit
                cparts[0] = BboBase.subSuitSym(cparts[0])
                # re-assemble
                contract = '-'.join(cparts)
                txt += f', {contract}'
            return txt
            
        def printParClassic(self):
            print(f'Par for board {bdnum}')
            self.computePar()
            functions.PrintDealerPar(ctypes.pointer(self.parResults))

        def cardsStr(self, player, suit):
            pass
            
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

        def getCardSet(self, playerIdx, suit):
            # in dds, player indices are N=0, E=1, S=2, W=3
            # but in our hand, the suits are always in order S, W, N, E
            handIdx = (playerIdx + 2) % 4
            # within a hand, suits are always S, H, D, C
            suitIdx = 'SHDC'.index(suit)
            return self.hands[handIdx].suits[suitIdx]
            
        # inner class Deal.Hand
        class Hand(object):
            def __init__(self):
                self.suits = []

            @staticmethod
            def cardRank(c):
                return '23456789TJQKA'.index(c)

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
                    result = result + ''.join(sorted(suit, reverse=True, key=self.cardRank))
                return result

            def __str__(self):
                result = ''
                for s in self.suits:
                    result = result + f'{s} '
                return result


