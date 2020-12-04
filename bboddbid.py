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
import bbobidparcalc

def nested_dict():
    return collections.defaultdict(nested_dict)



class BboDDBidReporter(BboBase):
    def appDescription(self):
        return 'BBO Tourney Double Dummy Par Analysis'

    def addParserArgs(self, parser):
        pass

    def childGenReport(self):
        BboDDParTravLine.importArgs(self.args)
        if self.args.debug:
            bbobidparcalc.DEBUG = True
            
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
            if self.args.onlyBoard is not None and bdnum != self.args.onlyBoard:
                continue
            print(f'Board {bdnum}', file=sys.stderr)
            BboDDParTravLine.printHandPlusDDTable(bdnum)
            for tline in self.travellers[bdnum]:
                print(f'<b>NS: {tline.north}-{tline.south} vs. EW: {tline.east}-{tline.west}</b>')
                bidParsList = tline.calcBiddingParList()
                # print(bidParsList, file=sys.stderr)
                # find out how many par changes are in the returned list
                parScore = bidParsList[0].parScore
                rowsNeeded = 1
                for bidparrec in bidParsList[1:]:
                    if bidparrec.bidder == 'W' or bidparrec.parScore != parScore:
                        rowsNeeded += 1
                    parScore = bidparrec.parScore
                cols = 5
                rows = 1 + 1 + rowsNeeded # pre-bid and header
                # print('rows/cols', bdnum, rows, cols, file=sys.stderr)
                # for rec in bidParsList:
                    # print(rec, file=sys.stderr)
                tab = [['' for i in range(cols)] for j in range(rows)]

                # now go thru list and fill out table
                # tab[0][0] = f'<b>Init:</b>'
                tab[1][4] = self.htmlNotesString(bidParsList[0])
                for (col, dir) in enumerate('NESW'):
                    tab[1][col] = f'<b>&nbsp;&nbsp;{dir}&nbsp;&nbsp;</b>'
                tab[0][4] = f'<b>Par</b>'
                parScore = bidParsList[0].parScore
                row = 2
                for bidparrec in bidParsList[1:]:
                    col = 'NESW'.index(bidparrec.bidder)
                    # print(bdnum, row, col, file=sys.stderr)
                    if bidparrec.parScore != parScore:
                        tab[row][4] = self.htmlNotesString(bidparrec)
                        bidPunctuation ='?'
                    else:
                        bidPunctuation = ' '
                    tab[row][col] = f'&nbsp;&nbsp;{bidparrec.bid.upper():2}{bidPunctuation}&nbsp;&nbsp;'
                    
                    if bidparrec.parScore != parScore or bidparrec.bidder == 'W':
                        # print(tab[row], file=sys.stderr)
                        row += 1
                    parScore = bidparrec.parScore
                        
                tableHtml = BboBase.genHtmlTable(tab, self.args, colalignlist=('center', 'center', 'center', 'center', 'left'))
                # fix up first row to span 4 cols
                if False:
                    tableHtml = re.sub('<td style="text-align: center;"', '<td colspan="4" style="text-align: right;"', tableHtml, count=1)
                    tableHtml = re.sub('<td style="text-align: center;"></td>', '', tableHtml, count=3)

                print(tableHtml)

                        
            if False:
                self.showOptimumLeadsAllContracts(bdnum)
                print()
                self.printResultsTable(bdnum)
        sys.exit(1)
        self.printHTMLClosing()

    def htmlNotesString(self, bidparrec):
        str = bidparrec.notesString()
        strlist = list(str)
        for (i, c) in enumerate(strlist):
            if c == ' ':
                strlist[i] = '&nbsp;'
            else:
                break
        return ''.join(strlist)
        
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

BboDDBidReporter().genReport()
