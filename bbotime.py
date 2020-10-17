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
import tabulate

from bbobase import BboBase, BboTravLineBase

map = {}
players = {}
partners = {}
opps = {}

class BboTimeReporter(BboBase):
    def appDescription(self):
        return 'BBO Tourney Time Analysis'

    def addParserArgs(self, parser):
        parser.add_argument('--tstart',  default=None, help='tournament start date/time')
        parser.add_argument('--simclocked', default=False, action='store_true', help='afterwards simulate as if clocked had been used')
        parser.add_argument('--rowsPerPlayer', default=1, type=int, help='rows per player in table')
        parser.add_argument('--tablefmt', default='pretty', help='tabulate table format')
        parser.add_argument('--minsPerBoard', default=6, type=int, help='minutes allowed per board (for simclocked)')

    def childGenReport(self):
        # build default start time from directory name (if start time not supplied in args)
        if self.args.tstart is None:
            head, sep, tail = self.args.dir.partition('/')
            if head == 'travs':
                self.args.tstart = tail + ' 15:00'

        self.initMap()

        # at this point the robot names are fixed up if they could be
        # so proceed as if there was no duplication of names
        BboTimeTravLine.importArgs(self.args)
        for bdnum in range (1, self.args.boards + 1):
            # place rows in big table indexed by boardnumber and North and East names
            for row in self.travTableData[bdnum]:
                self.addToMaps(bdnum, row)

        # With all files processed and in maps, go thru list of BboTimeTravLine objects
        # and compute WaitEndTime (for end of round tlines)
        # North and East point to same BboTimeTravLine object so only need to do one.
        for bdnum in range (1, self.args.boards + 1):
            # note only needed for end of round records and don't need last one
            if bdnum % self.args.bpr == 0 and bdnum != self.args.boards:
                for player in map[bdnum].keys():
                    tline = map[bdnum][player]
                    if player == tline.origNorth:
                        tline.computeWaitEndTime()

        # now startTimes
        for bdnum in range (1, self.args.boards + 1):
            for player in map[bdnum].keys():
                tline = map[bdnum][player]
                if player == tline.origNorth:
                    tline.addStartTime()
                    tline.iElapsed = tline.elapsed()

        if self.args.debug:
            self.printMap()

        self.printSummary(f'\nUnclocked Report for {self.args.tstart}')
        
        if self.args.simclocked:
            #  compute endTime using clocked algorithm
            nextEndTime = {}

            # for first board of each round, redo startTimes
            for bdnum in range (1, self.args.boards + 1):
                if bdnum % self.args.bpr == 1:
                    bdnumFirstInRound = bdnum
                    for player in map[bdnum].keys():
                        tline = map[bdnum][player]
                        tline.addStartTime()
                        nextEndTime[player] = tline.iStartTime             

                # for first and other boards, update iEndTime using existing iElapsed
                for player in map[bdnum].keys(): 
                    tline = map[bdnum][player]
                    unclockedEndTime = nextEndTime[player] + tline.iElapsed * 60
                    roundStartTime = map[bdnumFirstInRound][player].iStartTime
                    clockedEndTimeLimit = roundStartTime + self.args.minsPerBoard * self.args.bpr * 60
                    nextEndTime[player] = min(unclockedEndTime, clockedEndTimeLimit)
                    tline.iEndTime = nextEndTime[player]
                    if clockedEndTimeLimit < unclockedEndTime:
                        if self.args.debug:
                            print('exceed clocked time limit:', bdnum, player, (unclockedEndTime-roundStartTime)/60, (clockedEndTimeLimit-roundStartTime)/60)
                        tline.iElapsed -= (unclockedEndTime - clockedEndTimeLimit)/60
                        tline.clockedTruncation = True 
                    if self.args.debug:
                        print(f'bdnum {bdnum}, player {player}, {tline}')

                # if it's the last board in the round, now have proper iEndTime
                # and we can compute WaitEndTime for last tline in Round
                if bdnum % self.args.bpr == 0:
                    for player in map[bdnum].keys(): 
                        tline = map[bdnum][player]
                        if player == tline.origNorth:            
                            # print(bdnum, player, (tline.iEndTime-roundStartTime)/60)
                            tline.computeWaitEndTime(clockedAlg=True)

            if self.args.debug:
                self.printMap()
            self.printSummary(f'\n\nClocked Simulation for {self.args.tstart}')

    def initMap(self):
        for n in range(1, self.args.boards+1):
            map[n] = {}
            opps[n] = {}


    def addToMaps(self, bdnum, row):
        tline = BboTimeTravLine(bdnum, row)
        map[bdnum][tline.origNorth] = tline
        map[bdnum][tline.origEast] = tline
        players[tline.origNorth] = 1
        players[tline.origEast] = 1
        opps[bdnum][tline.origNorth] = tline.origEast
        opps[bdnum][tline.origEast] = tline.origNorth


    def printMap(self):
        for bdnum in range(1, self.args.boards+1):
            for k in sorted(map[bdnum].keys()):
                print(bdnum, map[bdnum][k])

    def printSummary(self, title):
        print(title)
        rounds = int(self.args.boards/self.args.bpr)
        numpairs = len(players)
        numtables = int(numpairs/2)
        numcols = rounds + 2  # add in name and totals
        self.hdrRows = numrows = 1 + numtables + 1
        numrows = self.hdrRows + numpairs * self.args.rowsPerPlayer
        self.tab = [['' for i in range(numcols)] for j in range(numrows)]
        self.addHeaderInfo()
        for (pidx, p) in enumerate(sorted(players.keys())):
            self.addPersonInfo(p, pidx)
        calist = []
        for n in range(numcols):
            calist.append('center')
        calist[0] = calist[-1] = 'right'
        print(tabulate.tabulate(self.tab, tablefmt=self.args.tablefmt, colalign=calist))
        
    # header for summaries
    def addHeaderInfo(self):
        self.tab[0][0] = 'Round->'
        self.tab[0][-1] = '-Totals-'
        # for each round put in round number followed by who played who
        for rnd in range(1, int(self.args.boards/self.args.bpr) + 1):
            self.tab[0][rnd] = f'    {rnd:2}     '
            bdnum = (rnd-1) * self.args.bpr + 1
            rowidx = 1
            for player in map[bdnum].keys():
                tline = map[bdnum][player]
                if tline.origNorth == player:
                    charsPerName = 3
                    self.tab[rowidx][rnd] = f'{tline.origNorth[0:charsPerName]}-{tline.origEast[0:charsPerName]}'
                    rowidx += 1
                    
    def addPersonInfo(self, player, pidx):
        row = self.hdrRows + pidx * self.args.rowsPerPlayer
        self.tab[row][0] = player
        totalPlay = 0
        totalWait = 0
        for rnd in range(1, int(self.args.boards/self.args.bpr) + 1):
            roundMins = self.roundElapsedMins(rnd, player)
            tlineLastInRound = map[rnd * self.args.bpr][player]
            waitMins = tlineLastInRound.waitMins()
            specialChar = ' ' if not tlineLastInRound.clockedTruncation else '*'
            col = rnd
            self.tab[row][col] = f'{int(roundMins):2}{specialChar}+{int(waitMins):2}'
            totalPlay += roundMins
            totalWait += waitMins
        self.tab[row][-1] = f'  {int(totalPlay):3} + {int(totalWait):2}'

    # return elapsedTime and waitTime for that round
    def roundElapsedMins(self, rnd, player):
        bdnumLastInRound = rnd * self.args.bpr
        bdnumFirstInRound = bdnumLastInRound - self.args.bpr + 1
        return (map[bdnumLastInRound][player].iEndTime - map[bdnumFirstInRound][player].iStartTime) / 60


class BboTimeTravLine(BboTravLineBase):
    def __init__(self, bdnum, row):
        super(BboTimeTravLine, self).__init__(bdnum, row)
        self.waitEndTime = self.iEndTime  # for end of round records this will be adjusted later
        self.clockedTruncation = False
        
    # for end of round tlines, compute dependenciesx
    def computeWaitEndTime(self, clockedAlg=False):
        deps = {}
        if clockedAlg:
            self.waitEndTime = 0  # will be computed from iEndTimes below
            # just include everyone as a dependency
            for player in map[self.bdnum].keys():
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
                if self.args.debug and self.bdnum / self.args.bpr == 1:
                    print('before', deps)
                newdeps = {}
                for dep in deps.keys():
                    thisRoundOpp = opps[self.bdnum][dep]
                    thisRoundOppsNextOpp = opps[self.bdnum+1][thisRoundOpp]
                    newdeps[thisRoundOpp] = 1
                    newdeps[thisRoundOppsNextOpp] = 1
                deps.update(newdeps)
                anotherPass = len(deps.keys()) > startlen
                if self.args.debug and self.bdnum / self.args.bpr == 1:
                    print('after', deps)

        # now find the maximum end time for the list of deps
        for dep in deps.keys():
            self.waitEndTime = max(self.waitEndTime, map[self.bdnum][dep].iEndTime)

                
    # addStartTime just uses prev round's end time, + any wait time for first boards in round
    def addStartTime(self):
        if self.bdnum == 1:
            self.iStartTime = self.readTime(self.args.tstart)
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

    
        
#-------- main stuff starts here -----------
BboTimeReporter().genReport()
    
