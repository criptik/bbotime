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
from bbobidparcalc import BiddingParCalc


def nested_dict():
    return collections.defaultdict(nested_dict)


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
        # and everything after
        s = re.sub('\|rh\|.*$', '', s)
        # replace suits with separators
        s = re.sub('S', '', s)
        s = re.sub('[HDC]', '.', s)
        s = s.lstrip(' ')
        s = s.rstrip(' ')
        str3Hands = s.split(',')[0:3]

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
        
    def linToPbnBidList(self):
        s = self.linStr
        splits = re.split('\|mb\|', s)
        splits = splits[1:-1]
        splits.append('p')
        # get rid of any alert parts
        for n in range(len(splits)):
            splits[n] = re.sub('\|an.*', '', splits[n])
        # print(splits, file=sys.stderr)
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
        # print(DDplayPBN.number, DDplayPBN.cards, file=sys.stderr)
        threadIndex = 0
        res = dds.AnalysePlayPBN(
            dlPBN,
            DDplayPBN,
            ctypes.pointer(solved),
            threadIndex)
        self.solvedPlayContents = ctypes.pointer(solved).contents
        # if there are 52 cards in the playstring, the solvedPlayContents stop at 48
        # (because on the last trick there are no choices to be made)
        # But when we format the play analysis, we would like to show all the tricks
        # that were played.  So here we check for the case that the playString (playCount)
        # is greater than the solvedPlayContents.number, and we add some dummy records
        # (there will never be DD expected trick changes in this last trick but at least we will see it).
        # -1, +1 logic below is because the first trickCount in solvedPLayContents
        # is the expected tricks taken before any cards are played.
        if self.playCount > self.solvedPlayContents.number - 1:
            numPlaysSolved = self.solvedPlayContents.number
            lastTricksVal = self.solvedPlayContents.tricks[numPlaysSolved-1]
            self.solvedPlayContents.number = self.playCount + 1
            for i in range(numPlaysSolved, self.playCount+1):
                self.solvedPlayContents.tricks[i] = lastTricksVal
                

    def declColor(self):
        return 'cyan'

    def defenderColor(self, dirLetter):
        return 'pink' if dirLetter in 'NE' else 'orange'

    def colorForDir(self, myLetter):
        myIndex = 'NESW'.index(myLetter)
        pardLetter = 'NESW'[(myIndex + 2) % 4]
        myColor = self.declColor() if self.decl == myLetter else None if self.decl == pardLetter else self.defenderColor(myLetter)
        return myColor
        
    def coloredName(self, myLetter):
        myColor = self.colorForDir(myLetter)
        myIndex = 'NESW'.index(myLetter)
        myName = self.playerDir[myIndex]
        myStyledName = myName if myColor is None else f'<span style="background-color:{myColor}">{myName}</span>'
        return myStyledName


    def replayButtonHtml(self):
        return f'&nbsp;&nbsp;&nbsp;&nbsp;<a href="https://dds.bridgewebs.com/bsol2/ddummy.htm?club=us_tomdeneau&lin={self.linStr}" target="_blank" class="button">Replay It</a>'

    def formatPlayAnalysis(self):
        # functions.PrintPBNPlay(ctypes.pointer(DDplayPBN), ctypes.pointer(solved))
        print(f'DD Expected Tricks: {self.solvedPlayContents.tricks[0]}')
        numPlays = self.solvedPlayContents.number
        rows = (((numPlays-1)+3)//4 * 4) // 4
        trickColCount = 4 
        cols = 1 + trickColCount + 1   # 1 for leader, 4 for cards/trick, 1 for button
        # print('numplays-', numPlays, ',rows=', rows, 'solved=', self.solvedPlayContents.tricks[numPlays-1], file=sys.stderr)
        tab = [['' for i in range(cols)] for j in range(rows)]
        # in addition to showing cards played, we also
        # now go thru and adjust the ones that involve trick count changes
        # now go thru and adjust the ones that involve trick count changes
        lasttrix = self.solvedPlayContents.tricks[0]
        # put in the replay it button in first row, last col
        tab[0][-1] = self.replayButtonHtml()
        # go thru solvedPlayContents
        rowLeader = None
        for i in range(1, numPlays):
            psidx = 2*(i-1)
            cellCard = self.playString[psidx : psidx+2]
            (cellSuit, cellRank) = cellCard
            cellCardLead = ''  if self.args.playTricksLeftRight else '&nbsp;' # add leading space sometimes
            # first in trick/row, determine leader
            r = (i-1)//4
            if (i-1)%4 == 0:
                rowLeader = self.dealInfos[self.bdnum].pbnDeal.playerHoldingCard(cellSuit, cellRank)
                # add leader in first column if condensed format
                if self.args.playTricksLeftRight:
                    tab[r][0] = f'{rowLeader}<sub>&nbsp;&nbsp</sub>'
                else:
                    cellCardLead = '&#10148;' # or alternative right ararow &#8594;
            cellCard =  cellCardLead + cellCard
            trickStartColumn = 1 if self.args.playTricksLeftRight else 1 + 'NESW'.index(rowLeader)
            # starting column depends on format type
            c = (i-1)%4 + trickStartColumn
            c = c-4 if c > 4 else c
            if not self.args.playTricksLeftRight:
                c = (c-1)%4 + 1
                # also show winner of previous trick
                if (i-1)%4 == 0 and r != 0:
                    tab[r-1][c] = re.sub('<sub', '*<sub', tab[r-1][c])
                    
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
        if self.args.playTricksLeftRight:
            myHeaders = ['Lead','','','','','']
        else:
            myHeaders = ['']
            for i in range(trickColCount):
                myLetter = 'NESW'[i%4]
                myColor = self.colorForDir(myLetter)
                # use declColor for both decl and dummy
                if myColor == None:
                    myColor = self.declColor()
                myHeaders.append( f'<span style="background-color:{myColor}">&nbsp;{myLetter}&nbsp;</span>&nbsp;')
            myHeaders.append('') # for last column
        # print(myHeaders, file=sys.stderr)
        # print(tab, file=sys.stderr)
        tableHtml = BboBase.genHtmlTable(tab, self.args, headers=myHeaders)
        print(tableHtml, end='')

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

    # print hand and DD table using outer html table
    @classmethod
    def printHandPlusDDTable(cls, bdnum):
        handStr = f'<pre>{cls.dealInfos[bdnum].getHandString()}</pre>'
        ddTableStr = f'<pre>{cls.dealInfos[bdnum].getDDTableStr("Double Dummy Table")}\n\n</pre>'
        # 3 cols, 1 row in outer table
        outtab = [['' for i in range(3)] for j in range(1)]             
        outtab[0][0] = handStr
        outtab[0][1] = '&nbsp;'
        outtab[0][2] = ddTableStr
        print(BboBase.genHtmlTable(outtab, cls.args))

    def calcBiddingParList(self):
        calc = BiddingParCalc(self.bdnum, self.dealInfos[self.bdnum])
        bidList = self.linToPbnBidList()
        return calc.calcParsForBidList(bidList)
        
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


        def getHandString(self):
            title = f'Board:{self.bdnum}    Vul:{self.getVulStr()}   Dlr:{self.getDealerStr()}'
            # call helper function with no title
            handStr = functions.getHandStringPBN(None, self.DDdealsPBN.deals[0].cards)
            handStr = BboBase.subSuitSym(handStr)
            return f'{title}\n{handStr}'

        def getDDTricks(self, suit, dir):
            suitidx = 'SHDCNT'.index(suit)
            diridx = 'NESW'.index(dir)
            if self.Testing:
                return ((suitidx + diridx) % 4) + 5
            table = ctypes.pointer(self.ddTable.results[0])
            return table.contents.resTable[suitidx][diridx]
            
        def getDDTableStr(self, title):
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
            tabstr = tabulate.tabulate(tabList, tablefmt='plain')
            return f'{title}\n{"-" * len(title)}\n{tabstr}\n\nPar:{self.parString()}\n'

        def printDDTableClassic(self):
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

        # get raw score possible for a suit and level and double situation
        # given that dd computed we can take trix number of tricks
        def getRawScore(self, suit, level, dblFlag, player, trix):
            downDblNotVulList = (0, 100, 300, 500, 800, 1100, 1400, 1700, 2000, 2300, 2600, 2900, 3200, 3500)
            downDblVulList    = (0, 200, 500, 800, 1100, 1400, 1700, 2000, 2300, 2600, 2900, 3200, 3500, 3800)

            vulIndex = self.getVulIndex()
            isVul = vulIndex == 1 or (player in 'NS' and vulIndex == 2) or (player in 'EW' and vulIndex == 3)
            # print(suit, level+6, trix, file=sys.stderr)
            if trix < level+6:
                # going down
                down = (level+6) - trix
                if dblFlag == 0:
                    score = down * 50 if not isVul else down * 100
                elif dblFlag == 1 or dblFlag == 2:
                    downList = downDblNotVulList if not isVul else downDblVulList
                    score = downList[down] * dblFlag
                return -1*score
            else:
                # making something
                gamebonus = 50
                slambonus = 0
                # making contract
                overtrix = (trix-6) - level
                ptsPerTrick = 20 if suit in 'DC' else 30
                trickOneBonus = 10 if suit == 'N' else 0
                bidTrickVal = trickOneBonus + level * ptsPerTrick * (2 ** dblFlag)
                if dblFlag == 0:
                    overTrickVal = overtrix * ptsPerTrick
                else:
                    overTrickVal = overtrix * (100 if not isVul else 200) * (dblFlag)
                if bidTrickVal >= 100:
                    gamebonus = 300 if not isVul else 500
                if level == 6:
                    slambonus = 500 if not isVul else 750
                elif level == 7:
                    slambonus = 1000 if not isVul else 1500
                insultVal = 50 * dblFlag
                return bidTrickVal + overTrickVal + gamebonus + slambonus + insultVal

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


