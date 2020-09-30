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
        Testing = False
        useSuitSym = True

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
                functions.PrintPBNHand(f'Board: {self.bdnum}', self.DDdealsPBN.deals[0].cards)
            else:
                title = f'Board:{self.bdnum}    Vul:{self.getVulStr()}   Dlr:{self.getDealerStr()}'
                # call helper function with no title
                handStr = functions.getHandStringPBN(None, self.DDdealsPBN.deals[0].cards)
                for suit in self.SuitSyms.keys():
                    handStr = re.sub(f'{suit} ', f'{self.SuitSyms[suit]} ', handStr)
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
                tabList[0][1 + sidx] = self.SuitSyms[suit] if self.useSuitSym and suit != 'NT' else suit
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
            return 'NEWS'[self.getDealerIndex()]
            
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
        
        def getPar(self):
            self.getDDTable()
            if self.parResults is None:
                self.computePar()

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
                txt += f', {pcontents.contracts[i].value.decode("utf-8")}'
            return txt
            
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


