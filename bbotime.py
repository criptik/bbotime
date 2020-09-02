# This script deduces the elapsed time and wait times from BBO
# traveller records for unclocked tournaments.  Since BBO only
# supplies the end time for each board in the traveller, we have to
# deduce the start time.  The start time is easy for the first round
# but after that we have to deduce when pairs actually get to move to
# the next round based on dependencies on other pairs, etc.

# From observations, it appears that not only must your opponent for
# the next round be finished (which is obvious), but also your
# opponent for the current round must be ready to move (which is not
# so obvious).  This is because I never saw a pair move and leave
# their previous opponents alone at a table waiting.  For example if
# round N has A-B, C-D, E-F and round N+1 has A-C, B-E, D-F, not only
# will A have to wait for C-D to finish, but also for B to move, which
# reques E-F to finish.  A corollary of this is that with 3 tables all
# moves for the next round require all 3 tables to be finished.

import sys
import time
import os
from pprint import pprint

from bboparse import BboParserBase, BboTravLineBase

global args

travTableData = []
map = {}
players = {}
partners = {}
opps = {}

class BboTimeParser(BboParserBase):
    def appDescription(self):
        return 'BBO Tourney Time Analysis'

    def addParserArgs(self, parser):
        parser.add_argument('--tstart',  default=None, help='tournament start date/time')
        parser.add_argument('--simclocked', default=False, action='store_true', help='afterwards simulate as if clocked had been used')

class BboTimeTravLine(BboTravLineBase):
    def __init__(self, bdnum, row):
        super(BboTimeTravLine, self).__init__(bdnum, row)
        self.waitEndTime = self.iEndTime  # for end of round records this will be adjusted later

    # for end of round tlines, compute dependenciesx
    def computeWaitEndTime(self, clockedAlg=False):
        deps = {}
        if clockedAlg:
            # just include everyone as a dependency
            for player in map[bdnum].keys():
                deps[player] = 1
        else:
            # normal unclocked logic, compute dependencies
            deps[self.origNorth] = 1
            # find our opp for next round and add that to the deps list
            nextRoundOpp = opps[self.bdnum+1][self.origNorth]
            deps[nextRoundOpp] = 1
            # in the normal algorithm a pair cannot advance unless it current opps can also advance
            anotherPass = True
            while anotherPass:
                startlen = len(deps.keys())
                if args.debug and self.bdnum / args.bpr == 1:
                    print('before', deps)
                newdeps = {}
                for dep in deps.keys():
                    thisRoundOpp = opps[self.bdnum][dep]
                    thisRoundOppsNextOpp = opps[self.bdnum+1][thisRoundOpp]
                    newdeps[thisRoundOpp] = 1
                    newdeps[thisRoundOppsNextOpp] = 1
                deps.update(newdeps)
                anotherPass = len(deps.keys()) > startlen
                if args.debug and self.bdnum / args.bpr == 1:
                    print('after', deps)

        # now find the maximum end time for the list of deps
        for dep in deps.keys():
            self.waitEndTime = max(self.waitEndTime, map[bdnum][dep].iEndTime)

    # addStartTime just uses prev round's end time, + any wait time for first boards in round
    def addStartTime(self):
        if self.bdnum == 1:
            self.iStartTime = self.readTime(args.tstart)
        else:
            prevTravNorth = map[self.bdnum-1][self.origNorth]
            self.iStartTime = prevTravNorth.waitEndTime

    def waitMins(self):
        return (self.waitEndTime - self.iEndTime) / 60
                
    def showtime(self, itime):
        return(time.strftime('%H:%M', time.localtime(itime)))

    def elapsed(self):
        return (self.iEndTime - self.iStartTime)/60
        
    def __str__(self):
        mystr = ('N:%15s, E:%15s, Start:%5s, End:%5s, Elapsed:%2d, Wait:%2d' % (self.origNorth, self.origEast,
                                                                                self.showtime(self.iStartTime),
                                                                                self.showtime(self.iEndTime),
                                                                                self.iElapsed, self.waitMins() ))
        return mystr

def initMap():
    for n in range(1, args.boards+1):
        map[n] = {}
        opps[n] = {}
        
        
def addToMaps(bdnum, row):
    tline = BboTimeTravLine(bdnum, row)
    map[bdnum][tline.origNorth] = tline
    map[bdnum][tline.origEast] = tline
    players[tline.origNorth] = 1
    players[tline.origEast] = 1
    opps[bdnum][tline.origNorth] = tline.origEast
    opps[bdnum][tline.origEast] = tline.origNorth
    

def printMap():
    for bdnum in range(1, args.boards+1):
        for k in sorted(map[bdnum].keys()):
            print(bdnum, map[bdnum][k])
        
# header for summaries
def printHeader():
    print('Round             ', end='')
    for r in range(1, int(args.boards/args.bpr) + 1):
        print(f'    {r:2}     ', end='')
    print('     Totals')

def printPersonSummary(player):
    print()
    print(f'{player:>15}  |  ', end = '')
    roundMins = 0
    totalPlay = 0
    totalWait = 0
    for bdnum in range(1, args.boards+1):
        tline = map[bdnum][player]
        roundMins = roundMins + tline.iElapsed
        waitMins = int(tline.waitMins())
        if bdnum % args.bpr == 0:
            print(f'{int(roundMins):2} +{int(waitMins):2}  |  ', end='')
            totalPlay = totalPlay + roundMins
            totalWait = totalWait + waitMins
            roundMins = 0
    print(f'  {int(totalPlay):3} + {int(totalWait):2}')

    
        
#-------- main stuff starts here -----------
myBboParser = BboTimeParser()
args = myBboParser.parseArguments()
    
# build default start time from directory name (if start time not supplied in args)
if args.tstart is None:
    head, sep, tail = args.dir.partition('-')
    if head == 'travs':
        args.tstart = tail + ' 15:00'

if False:
    print(args.__dict__)
    sys.exit(1)

initMap()
#read all traveler files into travTableData
travTableData = myBboParser.readAllTravFiles()

# at this point the robot names are fixed up if they could be
# so proceed as if there was no duplication of names
BboTimeTravLine.importArgs(args)
for bdnum in range (1, args.boards + 1):
    # place rows in big table indexed by boardnumber and North and East names
    for row in travTableData[bdnum]:
        addToMaps(bdnum, row)
    
# With all files processed and in maps, go thru list of BboTimeTravLine objects
# and compute WaitEndTime (for end of round tlines)
# North and East point to same BboTimeTravLine object so only need to do one.
for bdnum in range (1, args.boards + 1):
    # note only needed for end of round records and don't need last one
    if bdnum % args.bpr == 0 and bdnum != args.boards:
        for player in map[bdnum].keys():
            tline = map[bdnum][player]
            if player == tline.origNorth:
                tline.computeWaitEndTime()

# now startTimes
for bdnum in range (1, args.boards + 1):
    for player in map[bdnum].keys():
        tline = map[bdnum][player]
        if player == tline.origNorth:
            tline.addStartTime()
            tline.iElapsed = tline.elapsed()
            
if args.debug:
    printMap()

print(f'---------- Unclocked Report for game of {args.tstart} ----------------\n')

printHeader()
for p in sorted(players.keys()):
    printPersonSummary(p)

if args.simclocked:
    #  compute endTime using clocked algorithm
    nextEndTime = {}

    # for first board of each round, redo startTimes
    for bdnum in range (1, args.boards + 1):
        if bdnum % args.bpr == 1:
            for player in map[bdnum].keys():
                tline = map[bdnum][player]
                tline.addStartTime()
                nextEndTime[player] = tline.iStartTime             

        # for first and other boards, update iEndTime using existing iElapsed
        for player in map[bdnum].keys(): 
            tline = map[bdnum][player]
            nextEndTime[player] = nextEndTime[player] + tline.iElapsed * 60
            tline.iEndTime = nextEndTime[player]
            if args.debug:
                print(f'bdnum {bdnum}, player {player}, {tline}')

        # if it's the last board in the round, now have proper iEndTime
        # and we can compute WaitEndTime for last tline in Round
        if bdnum % args.bpr == 0:
            for player in map[bdnum].keys(): 
                tline = map[bdnum][player]
                if player == tline.origNorth:            
                    tline.computeWaitEndTime(clockedAlg=True)

        if bdnum == 6 and args.debug:
            print('\n===========end of Board 6============')
            printMap()
            
    if args.debug:
        printMap()
    print('\n\n----- Clocked Simulation Report -----')
    printHeader()
    for p in sorted(players.keys()):
        printPersonSummary(p)
    
