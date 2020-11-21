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
            return f'bd {self.bdnum}: Pass Out'
        ovunder = self.trix - (self.level + 6)
        ovunderStr = f'making {self.level + ovunder}' if ovunder >= 0 else f'down {-1*ovunder}'
        dblStr = ' ' if self.dblFlag == 0 else '*' * self.dblFlag
        return f'bd {self.bdnum}: NS {self.rawscore:+5}, {self.level}{self.suit}{dblStr} by {self.player:<2} {ovunderStr}'



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
    def getParRawScore(self, suit, level, pair, trix):
        dblFlag = 0 if trix >= (level + 6) else 1
        return self.dealInfo.getRawScore(suit, level, dblFlag, pair, trix)
        
    def calcPar(self, bids):
        self.trixdict = nested_dict()
        for suit in rankedSuits:
            for pair in ['NS', 'EW']:
                trixset = set()
                for dir in pair:
                    trix = self.dealInfo.getDDTricks(suit, dir)
                    self.trixdict[pair][suit][dir] = trix
                    trixset.add(trix)
                    
                # if both partners take same number of tricks, compress to one
                # (this is very common)
                if len(trixset) == 1:
                    self.trixdict[pair][suit] = {pair : trixset.pop()}


        # start with side making the next bid
        # the following are for the pre-bidding calculation
        pair = 'NS' if self.dealInfo.getDealerStr() in 'NS' else 'EW' 
        scoreToBeat = ScoreObj(self.bdnum, 0, 'C', '', pair, 0, 0)
        finished = False
        noChangeCount = 0
        bestScoreList = []
        while not finished:
            sawChange = False
            print(f'current side is {pair}, scoreToBeat is {scoreToBeat}', file=sys.stderr)
            # go thru self.trixdict and get scores
            # TODO: check for possible sacrifices,  etc
            for suit in rankedSuits:
                for player in self.trixdict[pair][suit].keys():
                    trix = self.trixdict[pair][suit][player]
                    level =  1 if trix <= 6 else self.startingLevel(suit, trix)
                    while not self.contractHigher(scoreToBeat.level, scoreToBeat.suit, level, suit):
                        level += 1
                        if level == 8:
                            break
                            
                    if level < 8:
                        rawscore = self.getParRawScore(suit, level, pair, trix)
                        if pair == 'EW':
                            rawscore *= -1
                        oldScore = scoreToBeat.rawscore
                        # print('contractHigher: ', scoreToBeat.level, scoreToBeat.suit, level, suit, trix, rawscore, oldScore, file=sys.stderr)
                        dblFlag = 1 if trix < level+6 else 0
                        if self.scoreIsBetter(oldScore, rawscore, pair):
                            scoreToBeat = ScoreObj(self.bdnum, level, suit, dblFlag, player, trix, rawscore)
                            # print('scoreIsBetter: ', oldScore, rawscore, player, scoreToBeat, file=sys.stderr)
                            bestScoreList = [scoreToBeat]
                            sawChange = True
                        elif oldScore == rawscore:
                            # ignore if matched score is just higher bid in same suit
                            if suit == scoreToBeat.suit and sideMap[player] == sideMap[scoreToBeat.player]:
                                pass
                            else:
                                scoreToBeat = ScoreObj(self.bdnum, level, suit, dblFlag, player, trix, rawscore)
                                # print('scoreIsSame: ', oldScore, rawscore, player, scoreToBeat, file=sys.stderr)
                                bestScoreList.append(scoreToBeat)
                                sawChange = True
                        else:
                            pass
                            # print('scoreIsNOTBetter: ', scoreToBeat.rawscore, rawscore, pair, file=sys.stderr)

            if False:
                print(f'self.trixdict for {pair}', file=sys.stderr)
                for suit in 'NSHDC':
                    for player in self.trixdict[pair][suit].keys():
                        print(f'{suit}, {player}, {self.trixdict[pair][suit][player]}', file=sys.stderr)

            # switch sides
            pair = 'NS' if pair == 'EW' else 'EW'
            noChangeCount = 0 if sawChange else noChangeCount + 1
            # print(sawChange, noChangeCount, file=sys.stderr)
            if noChangeCount >= 2:
                finished = True 

        # finished, show bestScores
        print('bestScoreList:', file=sys.stderr)
        for score in bestScoreList:
            print(score, file=sys.stderr)
        
