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

def doAssert(expected, got, testStr, detail):
    try:
        assert expected == got, str
    except AssertionError:
        print(f'assertion error on {testStr}')
        print(f'{detail}, expected {expected}, got {got}')
        # sys.exit(1)

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

import argparse

parser = argparse.ArgumentParser('bid par tester')
parser.add_argument('--only', type=int, default=None, help='only run this test')
args = parser.parse_args()

# A test is specified as a tuple with the following 4 elements:
#   a board number (affects dealer, vulnerability, etc.)
#   a default value for trix for any suit/player combination that is not specified
#   a trix specifier string of one or more of the form {dir}.{suit}.{trix}
#      dir will contain one or more of the directions (so NS.H.10 would mean both North and South can take 10 tricks at hearts)
#   a string specifying bids and expected results parsed as follows
#    * a number starting with + or - is a parscore which carries on until a different parscore is specified
#      at least one beginning parscore is required.
#    * a field in [] brackets is a set of contracts.  The contracts list is optional.
#      If not specified, the contracts returned by the test results are not checked, only the par score is checked.
#      If specified, it is assumed to carry on until a different contract set is specified.
#      Generally a contract set would be specified after a parscore.
#   * Anything else is a bid and will be added to the bidlist passed to calcParsForBidList.

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
    # try same thing with EW vulnerable, now sacrifice loses
    (3, 0, 'S.H.10 N.C.11 EW.S.8', '+420'),
    # similar but EW can make 9 tricks at spades
    (3, 0, 'S.H.10 N.C.11 EW.S.9', '+400'),
    # similar but NS can only make 10 tricks at clubs so they have to settle for the 4S sacrifice amount
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
    (1, 0, 'S.H.10 N.H.9',  '+420 1H +140'),
    # similar but South bids clubs first as well
    (1, 0, 'S.H.10 N.C.11 S.C.9', '+420 1H +400 P 2C +110'),
    # got too high so negative par
    (1, 0, 'S.H.10 N.C.11 S.C.7', '+420 1H +400 P 2C -100'),
    # 3N 5C dual contracts
    (1, 0, 'NS.N.9 N.C.11', '+400 [3N-NS,5C-N]'),
    # both sides make 3N??
    (1, 0, 'NSEW.N.9', '+100 [4N-EW]'),
    (2, 0, 'NSEW.N.9', '-200 [4N-NS]'),
    # part score battle where NS went too far (and EW did not double)
    (17, 0, 'NS.C.8 NS.S.8 EW.D.8 EW.H.8 EW.N.7', '''+100 [2N-EW,3D-EW,3H-EW]
                                                    P P 1C  P
                                                    1S P 2N   -100 [3C-S,3S-N]
                                                 P  3S        -100 [3S-N]
                                                       P 4S   -300 [4S-N]
                                                 P  P  P -100 [4S-N]
                                                  '''),
    # both sides can make 1NT, but passed out
    (1, 7, '', '+90 P -90 P +90 P -90 P +0'),
    # test double
    (1, 0, 'NSEW.N.7', '+90 1N D +100 [2N-EW] P P +180 [1N-N] P'),
    # test redouble
    (1, 0, 'NSEW.N.7', '+90 1N D +100 [2N-EW] R P P P +560 [1N-N]'),
    # test redouble
    (1, 0, 'NS.N.7', '+90 1N D +180 [1N-N] R +560 [1N-N] P P P'),
    # test best bid being redouble
    # not working yet
    # (1, 0, 'NS.N.7', '+90 1N D +560 [1N-N] P P P'),
    
] 	

for (testnum, testtup) in enumerate(tests):
    if args.only is not None and testnum != args.only:
        continue
    # print(f'test #{testnum}')
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
    exContracts = []
    lastConsList = []
    parScore = 0
    exScores.append(0)
    exContracts.append([])
    for cmd in re.split('\s+', bidResStr):
        # print(f'<{cmd}>')
        if len(cmd) == 0:
            continue
        if cmd[0] in '+-':
            parScore = int(cmd)
            # correct most recent expectedScore
            exScores[-1] = parScore
        elif cmd[0] == '[':
            # a list of contracts to parse
            # format is {level}{suit}-{decl}, comma separated
            cmd = cmd[1:-1]  # get rid of end brackets
            # print('cmd=', cmd)
            lastConsList = []
            if len(cmd) != 0:
                cons = re.split(',', cmd)
                # print('cons=', cons)
                for con in cons:
                    # print('con=', con)
                    (levsuit, decl) = con.split('-')
                    (levstr, suit) = levsuit
                    level = int(levstr)
                    myobj = (level, suit, decl)
                    lastConsList.append(myobj)
            exContracts[-1] = lastConsList
        else:
            # cmd is a bid
            bidList.append(cmd)
            exScores.append(parScore)
            exContracts.append(lastConsList)
            
    # print('expected stuff:', exScores, exContracts)
    
    testObj = BidParTester(bdnum, indict, trixdefault)
    calc = BiddingParCalc(bdnum, testObj)
    for (i, bidparrec) in enumerate(calc.calcParsForBidList(bidList)):
        # print(f'{i}: {bidparrec}')
        for obj in bidparrec.scoreList:
            pass
            # print(obj)
        # print('i=', i, exScores[i], exContracts[i])
        # see if complete match, start with score
        bidStr = 'Pre-Bid' if (i == 0) else f'after bid[{i}]={bidList[i-1]}'
        testStr = f'test# {testnum}, ({bdnum}, {trixdefault}, {dictStr}, {bidResStr}), {bidStr}'
        doAssert(exScores[i], bidparrec.parScore, testStr, 'parScore')
        # must check the contracts if any specified
        if len(exContracts[i]) > 0:
            doAssert(len(exContracts[i]), len(bidparrec.scoreList), testStr, 'number of contracts')
            for (j, con) in enumerate(exContracts[i]):
                (level, suit, decl) = con
                doAssert(level, bidparrec.scoreList[j].level, testStr, f'level[{j}]')
                doAssert(suit,  bidparrec.scoreList[j].suit,  testStr, f'suit[{j}]')
                doAssert(decl,  bidparrec.scoreList[j].player, testStr, f'declarer[{j}]')

