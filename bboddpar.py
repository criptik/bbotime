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
                tline.checkAndAppend(self.travellers)
        # print('travTableData and travellers are set up')

        # hand, ddtable and par display
        self.printHTMLOpening()
        for bdnum in range (1, self.args.boards + 1):
            # print(f'{bdnum:2}: {BboDDParTravLine.dealInfos[bdnum].pbnDealString}')
            handStr = f'<pre>{BboDDParTravLine.dealInfos[bdnum].getHandString()}</pre>'
            ddTableStr = f'<pre>{BboDDParTravLine.dealInfos[bdnum].getDDTableStr("Double Dummy Table")}\n\n</pre>'
            # 3 cols, 1 row in outer table
            outtab = [['' for i in range(3)] for j in range(1)]             
            outtab[0][0] = handStr
            outtab[0][1] = '&nbsp;'
            outtab[0][2] = ddTableStr
            print(BboBase.genHtmlTable(outtab, self.args))
            self.showOptimumLeadsAllContracts(bdnum)
            print()
            self.printResultsTable(bdnum)
        self.printHTMLClosing()

    @staticmethod
    def tlineScore(tline):
        return tline.nsScore
    
    def printResultsTable(self, bdnum):
        print()
        numResults = len(self.travellers[bdnum])
        rows = numResults
        cols = 8
        tab = [['' for i in range(cols)] for j in range(rows)]
        r = 0
        calist = ['left' for i in range(cols)]
        calist [3] = calist[4] = 'right'
        
        for tline in sorted(self.travellers[bdnum], reverse=True, key=self.tlineScore):
            tab[r][0:2] = [f'{tline.north}-{tline.south}&nbsp;', f'{tline.east}-{tline.west}&nbsp;']
            tab[r][2:4] = [f'{tline.resultStr}&nbsp;', f'{tline.nsPoints}&nbsp;', f'{tline.nsScore:5.2f}%', '']
            tab[r][-1] = tline.replayButtonHtml()
            r += 1
        print(BboBase.genHtmlTable(tab, self.args, colalignlist=calist))

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
