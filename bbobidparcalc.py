import sys
import time
import os
import collections
from pprint import pprint
from bbobase import BboBase

def nested_dict():
    return collections.defaultdict(nested_dict)

rankedSuits = 'CDHSN'
sideMap = {'E':'EW', 'W':'EW', 'EW':'EW', 'N':'NS', 'S':'NS', 'NS':'NS'}

DEBUG=False

def dbgprint(*args):
    if DEBUG:
        for (i, arg) in enumerate(args):
            leadspace = '' if i == 0 else ' '
            print(f'{leadspace}{arg}', end='', file=sys.stderr)
        print(file = sys.stderr)

def suitIndex(suit):
    return rankedSuits.index(suit)

class ScoreObj():
    def __init__(self, bdnum, level, suit, dblFlag, player, trix, rawscore):
        self.bdnum = bdnum
        self.level = level
        self.suit = suit
        self.dblFlag = dblFlag
        self.player = player
        self.trix = trix
        self.rawscore = rawscore

    def scoreSameSide(self, other):
        for sideset in [set('NS'), set('EW')]:
            if set(self.player).issubset(sideset):
                return set(other.player).issubset(sideset)


    def __str__(self):
        if self.level == 0:
            return f'0, Pass Out'
        ovunder = self.trix - (self.level + 6)
        ovunderStr = f'make {self.level + ovunder}' if ovunder >= 0 else f'down {-1*ovunder}'
        dblStr = ' ' if self.dblFlag == 0 else '*' * self.dblFlag
        return f'{self.rawscore:+5}, {self.level}{self.suit}{dblStr} by {self.player:<2} {ovunderStr}'

class BidParRec():
    def __init__(self, bid, bidder, scoreList):
        self.bid = bid
        self.bidder = bidder
        self.scoreList = scoreList
        self.textList = []
        # extract numeric score
        self.parScore = None
        for scoreObj in scoreList:
            (valtxt, txt) = f'{scoreObj}'.split(', ')
            self.parScore = int(valtxt)
            self.textList.append(txt)

    def bidString(self):
        return 'Pre-Bid: ' if self.bid is None else f'{self.bid:<2} by {self.bidder}: '

    def notesString(self):
        return f'{self.parScore:+5}, {" or ".join(self.textList)}'
    
    def __str__(self):
        strout = self.bidString()
        strout += self.notesString()
        return strout

class BiddingParCalc():
    def __init__(self, bdnum, dealInfo):
        self.bdnum = bdnum
        self.dealInfo = dealInfo

    
    @staticmethod
    def startingLevel(suit, trix):
        if trix >= 12:
            return trix-6
        if suit in 'CD' and trix == 11:
            return 5
        elif suit in 'HS' and trix >= 10:
            return 4
        elif suit in 'N' and trix >= 9:
            return 3
        else:
            return 1
        
    @staticmethod
    def scoreIsBetter(orig, other, pair):
        if pair == 'NS':
            return other > orig
        else:
            return other < orig

    @staticmethod
    def contractHigher(origlevel, origsuit, testlevel, testsuit):
        if suitIndex(testsuit) > suitIndex(origsuit):
            return testlevel >= origlevel
        else:
            return testlevel > origlevel

    # this gets the "Par Raw Score", i.e. where the other side
    # always doubles if it's going down and never doubles if it's making, etc.
    # for other double/redouble situations, one can call dealInfo.getRawScore directly
    def getParRawScore(self, suit, level, player, trix):
        dblFlag = 0 if trix >= (level + 6) else 1
        return self.getRawScoreSigned(suit, level, dblFlag, player, trix)
        
    def getRawScoreSigned(self, suit, level, dblFlag, player, trix):
        rawscore = self.dealInfo.getRawScore(suit, level, dblFlag, player, trix)
        if sideMap[player] == 'EW':
            rawscore *= -1
        # print('getRawScoreSigned:', suit, level, dblFlag, player, trix, rawscore, file=sys.stderr)
        return rawscore
        
    def buildInitialTrixDict(self):
        # build up initial trixdict
        self.trixdict = nested_dict()
        for suit in rankedSuits:
            for pair in ['NS', 'EW']:
                trixset = set()
                self.trixdict[pair][suit] = {}
                for dir in pair:
                    trix = self.dealInfo.getDDTricks(suit, dir)
                    self.trixdict[pair][suit][dir] = trix
                    trixset.add(trix)
                    
                # if both partners take same number of tricks, compress to one
                # (this is very common)
                if len(trixset) == 1:
                    self.trixdict[pair][suit] = {pair : trixset.pop()}

    def isPassedOut(self):
        return ((self.lastBid is not None and self.numConsecPasses == 3)
                or (self.lastBid is None and self.numConsecPasses == 4))
    
    def isNextToFinalPass(self):
        return ((self.lastBid is not None and self.numConsecPasses == 2)
                or (self.lastBid is None and self.numConsecPasses == 3))

    def doubleIsLegal(self, pair):
        # print('check doubIsLegal', self.lastBid, self.lastBidder, pair, file=sys.stderr)
        return(self.lastBid is not None
               and self.lastBid not in 'DR'
               and sideMap[self.lastBidder] != pair)
    
    # returns new scoreToBeat and affects sawChange boolean
    def checkScoreHigher(self, testScoreToBeat, scoreToBeat, pair):
        oldScore = scoreToBeat.rawscore
        if self.scoreIsBetter(oldScore, testScoreToBeat.rawscore, sideMap[pair]):
            dbgprint('scoreIsBetter: ', testScoreToBeat, scoreToBeat)
            self.bestScoreList = [testScoreToBeat]
            self.sawChange = True
            return testScoreToBeat
        elif oldScore == testScoreToBeat.rawscore:
            # ignore if matched score is just higher bid in same suit for something already in bestScoreList
            alreadyInList = False
            for scoreRec in self.bestScoreList:
                if testScoreToBeat.suit == scoreRec.suit and sideMap[testScoreToBeat.player] == sideMap[scoreRec.player]:
                    alreadyInList = True
            if alreadyInList:
                pass
            else:
                dbgprint('scoreIsSame: ', testScoreToBeat, scoreToBeat)
                self.bestScoreList.append(testScoreToBeat)
                self.sawChange = True
                # return first one, not last one
                return self.bestScoreList[0] 

        # if we got this far, no change due to this comparison
        # dbgprint('scoreIsNOTBetter: ', testScoreToBeat, scoreToBeat)
        return scoreToBeat
    
    def calcCurrentPar(self):
        # use trixdict to determine par contract
        # start with side making the next bid
        if self.bidder is None:
            # the following are for the pre-bidding calculation
            pair = 'NS' if self.dealInfo.getDealerStr() in 'NS' else 'EW' 
            self.savedScoreToBeat = scoreToBeat = ScoreObj(self.bdnum, 0, 'C', 0, pair, 0, 0)
        else:
            # select pair to be next after bidder
            pair = 'EW' if self.bidder in 'NS' else 'NS'
            scoreToBeat = self.savedScoreToBeat
        self.bestScoreList = []
        if self.isPassedOut():
            finished = True
        else:
            finished = False
            noChangeCount = 0
            self.sawChange = True # so first one gets printed
            checkedDouble = False
        while not finished:
            if True or self.sawChange:
                dbgprint(f'current side is {pair}, scoreToBeat is {scoreToBeat}')
            self.sawChange = False
            # note accepting the current scoreToBeat is like passing
            # in addition, we will check whether double or redouble (if legal) can improve par
            # go thru self.trixdict and get scores for suit bids
            if self.doubleIsLegal(pair) and not checkedDouble:
                # compute scoreToBeat doubled
                dblFlag = 1  # meaning doubled
                (level, suit) = self.lastBid
                level = int(level)
                player = self.declMap[sideMap[self.lastBidder]][suit]
                trix = self.trixdict[sideMap[player]][suit][player]
                dbgprint('Testing Double', pair, suit, level, dblFlag, player, trix)
                rawscore = self.getRawScoreSigned(suit, level, dblFlag, player, trix)
                testScoreToBeat = ScoreObj(self.bdnum, level, suit, dblFlag, player, trix, rawscore)
                scoreToBeat = self.checkScoreHigher(testScoreToBeat, scoreToBeat, pair)
                checkedDouble = True
            # go thru the suits starting with the next higher over scoreToBeat
            suitidx = rankedSuits.index(scoreToBeat.suit)
            for n in range(5):  # 5 suits
                suitidx = (suitidx + 1) % 5
                suit = rankedSuits[suitidx]
                for player in self.trixdict[pair][suit].keys():
                    trix = self.trixdict[pair][suit][player]
                    # find a level to test for this suit
                    level =  1 if trix <= 6 else self.startingLevel(suit, trix)
                    while not self.contractHigher(scoreToBeat.level, scoreToBeat.suit, level, suit):
                        # print('Contract is not higher:', level, suit, scoreToBeat, file=sys.stderr)
                        level += 1
                        if level == 8:
                            break
                            
                    if level < 8:
                        rawscore = self.getParRawScore(suit, level, player, trix)
                        dblFlag = 1 if trix < level+6 else 0
                        testScoreToBeat = ScoreObj(self.bdnum, level, suit, dblFlag, player, trix, rawscore)
                        scoreToBeat = self.checkScoreHigher(testScoreToBeat, scoreToBeat, pair)


            if False:
                print(f'self.trixdict for {pair}', file=sys.stderr)
                for suit in 'NSHDC':
                    for player in self.trixdict[pair][suit].keys():
                        print(f'{suit}, {player}, {self.trixdict[pair][suit][player]}', file=sys.stderr)

            # switch sides
            # handle case where final pass could end things
            # ie, there were already 2 passes and
            # the incoming scoreToBeat was better than anything we could get in a suit
            # in this case the other side doesn't get to try to improve anything
            if self.isNextToFinalPass() and not self.sawChange:
                finished = True
            else:
                pair = 'NS' if pair == 'EW' else 'EW'
                noChangeCount = 0 if self.sawChange else noChangeCount + 1
                # print('sawChange: ', self.sawChange, noChangeCount, file=sys.stderr)
                if noChangeCount >= 2:
                    finished = True 

        # finished, show bestScores
        if len(self.bestScoreList) == 0:
            self.bestScoreList.append(self.savedScoreToBeat)
        if DEBUG:
            print('bestScoreList: ', end='', file=sys.stderr)
            for score in self.bestScoreList:
                print(score, end=', ', file=sys.stderr)
            print(file=sys.stderr)
            
    def applyBidToTrixDict(self, bid, bidder):
        if bid in 'PDR' or len(bid) == 1:
            return
        (levstr, suit) = bid
        level = int(levstr)
        # find entry in trixdict and remove partner from possible declarer for this suit
        # if this is the first time this suit is being bid
        side = sideMap[bidder]
        if self.declMap[side].get(suit) is None:
            self.declMap[side][suit] = bidder
            bidderIdx = 'NESW'.index(bidder)
            bidderPard = 'NESW'[(bidderIdx + 2) % 4]
            newSuitDict = {}
            for player in self.trixdict[side][suit].keys():
                trix = self.trixdict[side][suit][player]
                newplayerstr = player.replace(bidderPard, '')
                if newplayerstr != player:
                    # print(f'before: {side} {suit} {self.trixdict[side][suit]}', file=sys.stderr)
                    if newplayerstr != '':
                        newSuitDict[newplayerstr] = trix
                else:
                    newSuitDict[player] = trix
            self.trixdict[side][suit] = newSuitDict    
            # print(f'after : {self.trixdict[side][suit]}', file=sys.stderr)
            # print('declMap:', self.declMap, file=sys.stderr)
                

    def addToBidParsList(self):
        # build tuple
        bid = None if len(self.bidParsList) == 0 else self.bidList[len(self.bidParsList) - 1]
        rec = BidParRec(bid, self.bidder, self.bestScoreList)
        self.bidParsList.append(rec)
        # print(self.bidParsList, file=sys.stderr)
        
    def calcParsForBidList(self, bidList):
        self.bidList = bidList
        self.buildInitialTrixDict()
        self.declMap = {'NS':{}, 'EW':{}}
        self.bidder = None
        self.lastBid = None
        self.lastBidder = None
        self.numConsecPasses = 0
        dbgprint(f'bd {self.bdnum}: Initial Par Pre-Bidding')
        self.bidParsList = []
        self.calcCurrentPar()
        self.addToBidParsList()
        dbgprint(f'bd:{self.bdnum}, bids={bidList}')
        bidderIdx = self.dealInfo.getDealerIndex()
        for bid in bidList:
            self.bidder = 'NESW'[bidderIdx]
            if bid != 'P':
                self.lastBid = bid
                self.lastBidder = self.bidder
                self.numConsecPasses = 0
            else:
                self.numConsecPasses += 1
                
            dbgprint(f'processing bid {bid} by {self.bidder}')
            self.applyBidToTrixDict(bid, self.bidder)
            # calculate scoreToBeat for next calcCurrentPar call
            if len(bid) > 1:
                (levstr, suit) = bid
                level = int(levstr)
                pair = 'NS' if self.bidder in 'NS' else 'EW'
                player = self.declMap[sideMap[self.bidder]][suit]
                trix = self.dealInfo.getDDTricks(suit, player)
                rawscore = self.getRawScoreSigned(suit, level, 0, player, trix)
                self.savedScoreToBeat = ScoreObj(self.bdnum, level, suit, 0, player, trix, rawscore)

            self.calcCurrentPar()
            self.addToBidParsList()
            # calc next bidder
            bidderIdx = (bidderIdx + 1) % 4
            
        return self.bidParsList
