import sys
import time
import os
import collections
from pprint import pprint
from bbobase import BboBase

def nested_dict():
    return collections.defaultdict(nested_dict)

rankedSuits = 'CDHSN'
othersideMap = {'E':'NS', 'W':'NS', 'EW':'NS', 'N':'EW', 'S':'EW', 'NS':'EW'}

def suitIndex(suit):
    return rankedSuits.index(suit)

class TrixScoreObj():
    def __init__(self, trix):
        self.trix = trix
        self.score = -9999
        
    def __str__(self):
        return f'trix:{self.trix}, score:{self.score}'

class ScoreObj():
    def __init__(self, bdnum, level, suit, player, trix, rawscore):
        self.bdnum = bdnum
        self.level = level
        self.suit = suit
        self.player = player
        self.trix = trix
        self.rawscore = rawscore

    def scoreSameSide(self, other):
        for sideset in [set('NS'), set('EW')]:
            if set(self.player).issubset(sideset):
                return set(other.player).issubset(sideset)


    def __str__(self):
        return f'bd {self.bdnum}: {self.level}{self.suit} by {self.player}, {self.trix}, {self.rawscore}'



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

    def calcPar(self):
        trixdict = nested_dict()
        for suit in rankedSuits:
            for pair in ['NS', 'EW']:
                trixset = set()
                for dir in pair:
                    trix = self.dealInfo.getDDTricks(suit, dir)
                    trixdict[pair][suit][dir] = TrixScoreObj(trix)
                    trixset.add(trix)
                    
                # if both partners take same number of tricks, compress to one
                # (this is very common)
                if len(trixset) == 1:
                    trixdict[pair][suit] = {pair : TrixScoreObj(trixset.pop())}


        # start with either side, it doesn't matter
        pair = 'NS' 
        scoreToBeat = ScoreObj(self.bdnum, 0, 'C', pair, 0, 0)
        finished = False
        noChangeCount = 0
        bestScoreList = []
        while not finished:
            sawChange = False
            print(f'current side is {pair}, scoreToBeat is {scoreToBeat}', file=sys.stderr)
            # go thru trixdict and get scores
            # TODO: check for possible sacrifices,  etc
            for suit in rankedSuits:
                for player in trixdict[pair][suit].keys():
                    trixObj = trixdict[pair][suit][player]
                    trix = trixObj.trix
                    level =  1 if trix <= 6 else self.startingLevel(suit, trix)
                    while not self.contractHigher(scoreToBeat.level, scoreToBeat.suit, level, suit):
                        level += 1
                        if level == 8:
                            break
                            
                    if level < 8:
                        # print('contractHigher: ', scoreToBeat.level, scoreToBeat.suit, level, suit, file=sys.stderr)
                        rawscore = self.dealInfo.getRawScore(suit, level, trix)
                        if pair == 'EW':
                            rawscore *= -1
                        trixObj.score = rawscore
                        oldScore = scoreToBeat.rawscore
                        if self.scoreIsBetter(oldScore, rawscore, pair):
                            scoreToBeat = ScoreObj(self.bdnum, level, suit, pair, trix, rawscore)
                            print('scoreIsBetter: ', oldScore, rawscore, pair, scoreToBeat, file=sys.stderr)
                            bestScoreList = [scoreToBeat]
                            sawChange = True
                        elif oldScore == rawscore:
                            scoreToBeat = ScoreObj(self.bdnum, level, suit, pair, trix, rawscore)
                            print('scoreIsSame: ', oldScore, rawscore, pair, scoreToBeat, file=sys.stderr)
                            bestScoreList.append(scoreToBeat)
                            sawChange = True
                        else:
                            pass
                            # print('scoreIsNOTBetter: ', scoreToBeat.rawscore, rawscore, pair, file=sys.stderr)

            if False:
                print(f'trixdict for {pair}', file=sys.stderr)
                for suit in 'NSHDC':
                    for player in trixdict[pair][suit].keys():
                        print(f'{suit}, {player}, {trixdict[pair][suit][player]}', file=sys.stderr)

            pair = othersideMap[pair]
            noChangeCount = 0 if sawChange else noChangeCount + 1
            # print(sawChange, noChangeCount, file=sys.stderr)
            if noChangeCount >= 2:
                finished = True 

        # finished, show bestScores
        print('bestScoreList:', file=sys.stderr)
        for score in bestScoreList:
            print(score, file=sys.stderr)
        
