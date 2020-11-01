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
import hands

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
        self.travellers = {}

        for bdnum in range (1, self.args.boards + 1):
            self.travellers[bdnum] = []
            for row in self.travTableData[bdnum]:
                tline = BboDDParTravLine(bdnum, row, self.travParser)
                # tline.getDDTable()
                self.travellers[bdnum].append(tline)
        # print('travTableData and travellers are set up')

        # hand, ddtable and par display
        if True:
            for bdnum in range (1, self.args.boards + 1):
                # print(f'{bdnum:2}: {BboDDParTravLine.dealInfos[bdnum].pbnDealString}')
                BboDDParTravLine.dealInfos[bdnum].printHand()
                BboDDParTravLine.dealInfos[bdnum].printTable()
                self.showOptimumLeadsAllContracts(bdnum)
                print()

    def showOptimumLeadsAllContracts(self, bdnum):
        print('Optimum Leads for Bid Contracts')
        print('-------------------------------')
        # only need to show "different" contracts
        # where "different" means just trump and declarer (level insignificant)
        contractMap = {}
        for tline in self.travellers[bdnum]:
            if tline.trumpstr is not None:
                trumpStr = self.subSuitSym(tline.trumpstr)
                trumpStr = 'NT' if trumpStr == 'N' else f' {trumpStr}'
                key = f'{trumpStr} by {tline.decl}'
                contractMap[key] = tline

        # now for each different contract show optimum leads
        for key in contractMap.keys():
            tline = contractMap[key]
            futs = tline.getOptimumLeads()
            optLeadStr = self.getOptLeadStr(futs, tline)
            print(f' {key}: {optLeadStr}')
        print()

    def getOptLeadStr(self, futs, tline):
        futcon = ctypes.pointer(futs).contents
        cardMap = {}
        for suit in 'SHDC':
            cardMap[suit] = 0
        for i in range(futcon.cards):
            res = ctypes.create_string_buffer(15)
            # add the returned rank into the "Holding"
            holdingVal = futcon.equals[i] | (1 << futcon.rank[i])
            suitChr = self.getSuitChr(futcon.suit[i])
            cardMap[suitChr] |= holdingVal
            # print(suitChr, self.getRankChr(futcon.rank[i]), futcon.rank[i], futcon.equals[i], holdingVal, cardMap[suitChr])

        totalOpts = 0
        optStr = ''
        for suit in 'SHDC':
            holdingVal = cardMap[suit]
            if holdingVal != 0:
                holdingStr = self.holdingToStr(holdingVal)
                holdingSet = set(holdingStr)
                handSet = BboDDParTravLine.dealInfos[tline.bdnum].pbnDeal.getCardSet(tline.getLeaderIndex(), suit)
                cardStr = 'any' if holdingSet == handSet else holdingStr
                suitSym = self.subSuitSym(suit)
                optStr += f'{suitSym}:{cardStr} '
                totalOpts += len(holdingStr)
                
        return 'any card' if totalOpts >= 13 else optStr

    @staticmethod
    def getSuitChr(idx):
        return 'SHDCN'[idx]

    @staticmethod
    def getRankChr(idx):
        return 'xx23456789TJQKA'[idx]

    def holdingToStr(self, holding):
        str = ''
        for i in range(14, 1, -1):
            if holding & (1 << i) != 0:
                str += self.getRankChr(i)
        return str

#-------- main stuff starts here -----------

BboDDParReporter().genReport()
