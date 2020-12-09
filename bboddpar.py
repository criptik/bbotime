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
from bboddbid import BboDDBidReporter
from bboddplay import BboDDPlayReporter

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

        self.boardList = range (1, self.args.boards + 1) if self.args.onlyBoard is None else [self.args.onlyBoard]
        for bdnum in self.boardList:
            self.travellers[bdnum] = []
            for row in self.travTableData[bdnum]:
                tline = BboDDParTravLine(bdnum, row, self.travParser)
                # tline.getDDTable()
                tline.checkAndAppend(self.travellers)
        # print('travTableData and travellers are set up')

        # hand, ddtable and par display
        self.printHTMLOpening()
        self.printButtonScript()
        bidReporter = BboDDBidReporter()
        playReporter = BboDDPlayReporter()
        bidReporter.args = playReporter.args = self.args
        self.printPairResultsTables()
        for bdnum in self.boardList:
            print(f'Board {bdnum}', file=sys.stderr)
            BboDDParTravLine.printHandPlusDDTable(bdnum)
            self.showOptimumLeadsAllContracts(bdnum)
            print()
            self.printBoardTraveller(bdnum)
            for tline in sorted(self.travellers[bdnum], reverse=True, key=self.tlineScore):
                self.printDivOpening(tline)
                bidReporter.printBidDetailsTable(tline)
                playReporter.printPlayDetailsTable(bdnum, tline)
                self.printDivClosing()
        self.printHTMLClosing()

    def printDivOpening(self, tline):
        divId = self.getDivId(tline)
        print(f'<div id="{divId}" style="display:none">')
        
    def printDivClosing(self):
        print('</div>')

    def printPairResultsTables(self):
        pairBoards = {}
        # make list of tlines for each pair
        for bdnum in self.boardList:
            for tline in self.travellers[bdnum]:
                nskey = f'{tline.north}-{tline.south}'
                ewkey = f'{tline.east}-{tline.west}'
                for key in [nskey, ewkey]:
                    if self.args.names is None:
                        found = True
                    else:
                        found = False
                        for name in self.args.names:
                            if name in key:
                                found = True
                                break
                    if found:
                        blist = pairBoards.get(key, [])
                        blist.append(tline)
                        pairBoards[key] = blist
        headers = ['Bd', 'Bid', 'Score', 'Pct', 'Direction']
        rows = len(self.boardList)
        cols = len(headers) 
        tab = [['' for i in range(cols)] for j in range(rows)]
        for pair in sorted(pairBoards.keys()):
            print(pair, '\n--------', file=sys.stderr)
            print(f'<b>Boards for {pair}</b>')
            pairnames = pair.split('-')
            bgColors = ['white']
            for (r, tline) in enumerate(sorted(pairBoards[pair], reverse=True, key=lambda tline: tline.pctScoreForName(pairnames[0]))):
                direction = 'NS' if tline.directionForName(pairnames[0]) in 'NS' else 'EW'
                oppNames = f'{tline.east}-{tline.west}' if direction == 'NS' else f'{tline.north}-{tline.south}'
                bgColors.append('white' if tline.decl is None else
                                'cyan' if tline.decl in direction else
                                'lightpink')
                    
                tab[r] = [f'<a href="#Board{tline.bdnum}">{tline.bdnum:2}</a>',
                          tline.resultStr,
                          f'{tline.nsPoints if direction == "NS" else -1 * tline.nsPoints}',
                          f'&nbsp;&nbsp;{tline.pctScoreForName(pairnames[0]):6.2f}%',
                          f'&nbsp;&nbsp;{direction} vs. {oppNames}'
                          ]
                # print(tline.bdnum, direction, tline.pctScoreForName(pairnames[0]), tline.nsScore, file=sys.stderr)
            # print('\n', file=sys.stderr)
            tabHtml = BboBase.genHtmlTable(tab, self.args, headers=headers)
            # now patch up the <tr> to show bgColor
            # print(bgColors, file=sys.stderr)
            for n in range(rows + 1):
                tabHtml = re.sub('<tr>', f'<tr style="background-color:{bgColors[n]}">', tabHtml, count=1)
            print(tabHtml)
            
    @staticmethod
    def tlineScore(tline):
        return tline.nsScore
    
    def printBoardTraveller(self, bdnum):
        print('<b>')
        numResults = len(self.travellers[bdnum])
        rows = numResults
        cols = 8
        tab = [['' for i in range(cols)] for j in range(rows)]
        r = 0
        calist = ['left' for i in range(cols)]
        calist [3] = calist[4] = 'right'
        
        for tline in sorted(self.travellers[bdnum], reverse=True, key=self.tlineScore):
            tab[r][0:2] = [f'{tline.north}-{tline.south}&nbsp;', f'{tline.east}-{tline.west}&nbsp;']
            tab[r][2:4] = [f'{tline.resultStr}&nbsp;', f'{tline.nsPoints}&nbsp;', f'{tline.nsScore:5.2f}%&nbsp;', f'{(100-tline.nsScore):5.2f}%&nbsp;']
            tab[r][-1] = f'{tline.replayButtonHtml()}&nbsp;&nbsp;{self.detailsButtonHtml(tline)}'
            r += 1
        print(BboBase.genHtmlTable(tab, self.args, colalignlist=calist))
        print('</b>')

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

    @staticmethod
    def getDivId(tline):
        return f'B{tline.bdnum}-{tline.north}'
    
    def detailsButtonHtml(self, tline):
        divId = self.getDivId(tline)
        return f'<button class="button" onclick="toggler(\'{divId}\')"><b>Details</b></button>'
        
    def printButtonScript(self):
        print('''
 <script>
 function toggler(id) {
     var divs = document.getElementsByTagName("div");
     for (elem of divs) {
         elem.style.display = "none";
     }
     var x = document.getElementById(id);
     x.style.display = "block";
 }
 </script>
''')
        

#-------- main stuff starts here -----------

if __name__ == '__main__':
    BboDDParReporter().genReport()
