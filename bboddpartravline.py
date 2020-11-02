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

    def __init__(self, bdnum, row, travParser):
        super(BboDDParTravLine, self).__init__(bdnum, row, travParser)
        # convert the captured LIN string into a pbn deal specification
        if self.dealInfos.get(bdnum) is None:
            self.dealInfos[bdnum] = self.DealInfo(self.bdnum, self.linToPbnDeal())
        (self.playString, self.claimed) = self.linToPbnPlayString()
        # print(f'bdnum {bdnum}, playstring={self.playString}')
        self.playCount = int(len(self.playString)/2)
        
    def linToPbnDeal(self):
        s = self.linStr
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
        # the three hands from str3Hands are always in order S, W, N (E missing)
        hands = {}
        for i in range(3):
            hands['SWN'[i]] = self.Deal.Hand.fromPbnHandStr(str3Hands[i])
        mydeal = self.Deal(hands)
        return mydeal
    
    def linToPbnPlayString(self):
        s = self.linStr
        # get rid of everything up to play info
        s = re.sub('^.*?pc\|', '|pc|', s)
        # strip down to only the cards played (get rid of |pc|)
        s = re.sub('\|pc\|', '', s)
        # get rid of any zz and following records at the end
        s = re.sub('\|zz\|.*?$', '', s)
        # string returned could have claim info at end, if so break that out
        splits = re.split('\|mc\|', s)
        if len(splits) == 1:
            splits.append(None)   # no claim info
        else:
            barsplits = splits[1].split('|')
            splits[1] = int(barsplits[0])  # amount claimed
        return splits
        
    def getDDTable(self):
        dealInfo = self.dealInfos[self.bdnum]
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
        dealInfo = self.dealInfos[self.bdnum]
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
        if self.args.debug:
            print('playstring len is ', len(self.playString), self.playString)
        DDplayPBN.cards = self.playString.encode('utf-8')
        # print(DDplayPBN.number, DDplayPBN.cards)
        threadIndex = 0
        res = dds.AnalysePlayPBN(
            dlPBN,
            DDplayPBN,
            ctypes.pointer(solved),
            threadIndex)
        self.solvedPlayContents = ctypes.pointer(solved).contents

    def declColor(self):
        return 'cyan'

    def defenderColor(self, dirLetter):
        return 'pink' if dirLetter in 'NE' else 'orange'
    
    def coloredName(self, myLetter):
        myIndex = 'NESW'.index(myLetter)
        pardLetter = 'NESW'[(myIndex + 2) % 4]
        myColor = self.declColor() if self.decl == myLetter else None if self.decl == pardLetter else self.defenderColor(myLetter)
        myName = self.playerDir[myIndex]
        myStyledName = myName if myColor is None else f'<span style="background-color:{myColor}">{myName}</span>'
        return myStyledName
                
    def formatPlayAnalysis(self):
        # functions.PrintPBNPlay(ctypes.pointer(DDplayPBN), ctypes.pointer(solved))
        print(f'DD Expected Tricks: {self.solvedPlayContents.tricks[0]}')
        numPlays = self.solvedPlayContents.number
        rows = ((numPlays+3)//4 * 4) // 4
        cols = 4 + 1
        tab = [['' for i in range(cols)] for j in range(rows)]
        # in addition to showing cards played, we also
        # now go thru and adjust the ones that involve trick count changes
        # now go thru and adjust the ones that involve trick count changes
        lasttrix = self.solvedPlayContents.tricks[0]
        for i in range(1, self.solvedPlayContents.number):
            psidx = 2*(i-1)
            r = (i-1)//4
            c = (i-1)%4 + 1
            cellCard = self.playString[psidx : psidx+2]
            (cellSuit, cellRank) = cellCard
            trix = self.solvedPlayContents.tricks[i]
            if trix == lasttrix:
                tab[r][c] = f'{cellCard}<sub>&nbsp;&nbsp</sub>'
            else:
                # add some color to this cell
                if trix < lasttrix:
                    bgcolor = self.declColor()
                else:
                    # defense error, show which one based on who played the card
                    player = self.dealInfos[self.bdnum].pbnDeal.playerHoldingCard(cellSuit, cellRank)
                    bgcolor = self.defenderColor(player)
                tab[r][c] = f'<span style="background-color:{bgcolor}">{cellCard}<sub> {trix:2}</sub>'
                lasttrix = trix
            # add leader in first column if this is first card of trick
            if c == 1:
                leader = self.dealInfos[self.bdnum].pbnDeal.playerHoldingCard(cellSuit, cellRank)
                tab[r][0] = f'{leader}&nbsp;&nbsp'
        # set this false if using some older version of tabulate which doesn't support unsafehtml tablefmt
        if not self.args.avoidUnsafeHtml:
            tableHtml = tabulate.tabulate(tab, tablefmt='unsafehtml')
        else:
            # if unsafeHtml doesn't work we have to use html and unescape a bunch of stuff
            tableHtml = tabulate.tabulate(tab, tablefmt='html')
            tableHtml = self.unescapeInnerHtml(tableHtml)
        print(tableHtml, end='')

    def unescapeInnerHtml(self, str):
        str = re.sub('&lt;', '<', str)
        str = re.sub('&gt;', '>', str)
        str = re.sub('&quot;', '"', str)
        str = re.sub('&amp;', '&', str)
        str = re.sub('&#x27;', "'", str)
        return str
        
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
                # fill in missing hand (from BBO generally E)
                missDir = (set('NSEW') - set(self.hands.keys())).pop()
                missHand = self.Hand.allCards()
                for hand in self.hands.values():
                    for i in range(len(hand.suits)):
                        missHand.suits[i] -= hand.suits[i]
                self.hands[missDir] = missHand

        def handOrder(self):
            return 'SWNE'
        
        def toPbnString(self):
            result = 'S:'  # BBO deals always start with 'S'
            for dir in self.handOrder():
                sep = ' ' if dir != 'S' else ''
                result += sep + self.hands[dir].toPbnString()
            return result

        def getSuitIdx(self, suit):
            return 'SHDC'.index(suit)
            
        def getCardSet(self, playerIdx, suit):
            # in dds, player indices are N=0, E=1, S=2, W=3
            dir = 'NESW'[playerIdx]
            # within a hand, suits are always S, H, D, C
            suitIdx = self.getSuitIdx(suit)
            return self.hands[dir].suits[suitIdx]

        def playerHoldingCard(self, suit, rank):
            # suit and rank are both strings
            suitIdx = self.getSuitIdx(suit)
            for dir in self.hands.keys():
                if rank in self.hands[dir].suits[suitIdx]:
                    return dir
            # if we got this far, we didn't find it
            return None
                    
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


