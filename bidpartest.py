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
# from bbobase import BboBase
from bboddpartravline import BboDDParTravLine
from bbobidparcalc import BiddingParCalc


hands = {}
handStr = 'AKQJT98765432...'
for dir in 'NSE':
    hands[dir] = BboDDParTravLine.Deal.Hand.fromPbnHandStr(handStr)
    handStr = handStr[-1] + handStr[:-1]
dummyDeal = BboDDParTravLine.Deal(hands)

class BidParTester(BboDDParTravLine.DealInfo):
    def __init__(self, bdnum, indict, default):
        # note: the pbn string here is irrelevant
        super(BidParTester, self).__init__(bdnum, dummyDeal)
        self.default = default
        self.dict = {}
        for dir in 'NSEW':
            self.dict[dir] = {}
        for key in indict.keys():
            (dir, suit) = key
            self.dict[dir][suit] =indict[key]

    def getDDTricks(self, suit, dir):
        trix = self.dict[dir].get(suit, self.default)
        return trix
        
    def __str__(self):
        str = ''
        for dir in 'NSEW':
            for suit in 'CDHSN':
                str += f'{self.getDDTricks(suit, dir):2} '
            str += '\n'
        return str

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


tests = [
    # no one making anything, should be passout
    (1, 6, '', '+0'),
    # both sides can make 1NT, dealer gets it
    (1, 7, '', '+90'),
    # bdnum 2, dealer is EW
    (2, 7, '', '-90'),
    # classic NS makes 4H or 5C
    (1, 0, 'S.H.10 N.C.11', '+420'),
    # with EW having sacrifice at 4S pushes up to 5C
    (1, 0, 'S.H.10 N.C.11 EW.S.8', '+400'),
    # try same thing with EW vulnerable
    (3, 0, 'S.H.10 N.C.11 EW.S.8', '+420'),
    # similar but EW can make 9 tricks at spades
    (3, 0, 'S.H.10 N.C.11 EW.S.9', '+400'),
    # similar but NS can only make 10 tricks at clubs
    (3, 0, 'S.H.10 N.C.10 EW.S.9', '+200'),
    # only 9 tricks at !h
    (3, 0, 'S.H.9 N.C.10 EW.S.9', '+130'),
    # only 8 tricks at !s for EW
    (3, 0, 'S.H.9 N.C.10 EW.S.8', '+140'),
    # same thing but no one vul
    (1, 0, 'S.H.9 N.C.10 EW.S.8', '+130'),
    # confirm things work when switch directions
    (1, 0, 'E.H.9 W.C.10 NS.S.8', '-130'),
    # North bidding !H first, only South can make
    (1, 0, 'S.H.10 N.C.11', '+420 1H +400'),
    (1, 0, 'S.H.10 N.C.10', '+420 1H +130'),
    # similar but South bids clubs first as well
    (1, 0, 'S.H.10 N.C.11 S.C.9', '+420 1H +400 P 2C +110'),
    # got too high so negative par
    (1, 0, 'S.H.10 N.C.11 S.C.7', '+420 1H +400 P 2C -100'),
    ]

for testtup in tests:
    (bdnum, trixdefault, dictStr, bidResStr) = testtup
    # build up indict by parsing dictStr
    indict = {}
    for cmd in re.split('\s+', dictStr):
        if len(cmd) == 0:
            continue
        # print(f'dictCmd={cmd}')
        (dirstr, suit, trix) = cmd.split('.')
        trix = int(trix)
        for dir in dirstr:
            indict[f'{dir}{suit}'] = trix

    # parse bidResStr to get bids and expected Results
    bidList = []
    exScores = []
    parScore = 0
    exScores.append(0)
    for cmd in re.split('\s+', bidResStr):
        if cmd[0] in '+-':
            parScore = int(cmd)
            # correct most recent expectedScore
            exScores[-1] = parScore
        else:
            # cmd is a bid
            bidList.append(cmd)
            exScores.append(parScore)
            
        
    
    testObj = BidParTester(bdnum, indict, trixdefault)
    calc = BiddingParCalc(bdnum, testObj)
    for (i, bidparrec) in enumerate(calc.calcParsForBidList(bidList)):
        assert bidparrec.parScore == exScores[i], f'on test ({bdnum}, {trixdefault}, {indict}, {bidList}) result {i} got {bidparrec.parScore:+}, expected {exScores[i]:+}'
      
