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

        print(f'---------- Unclocked Report for game of {self.args.tstart} ----------------\n')
        self.printSummary()
        
        if self.args.simclocked:
            #  compute endTime using clocked algorithm
            nextEndTime = {}

            # for first board of each round, redo startTimes
            for bdnum in range (1, self.args.boards + 1):
                if bdnum % self.args.bpr == 1:
                    for player in map[bdnum].keys():
                        tline = map[bdnum][player]
                        tline.addStartTime()
                        nextEndTime[player] = tline.iStartTime             

                # for first and other boards, update iEndTime using existing iElapsed
                for player in map[bdnum].keys(): 
                    tline = map[bdnum][player]
                    nextEndTime[player] = nextEndTime[player] + tline.iElapsed * 60
                    tline.iEndTime = nextEndTime[player]
                    if self.args.debug:
                        print(f'bdnum {bdnum}, player {player}, {tline}')

                # if it's the last board in the round, now have proper iEndTime
                # and we can compute WaitEndTime for last tline in Round
                if bdnum % self.args.bpr == 0:
                    for player in map[bdnum].keys(): 
                        tline = map[bdnum][player]
                        if player == tline.origNorth:            
                            tline.computeWaitEndTime(clockedAlg=True)

                if bdnum == 6 and self.args.debug:
                    print('\n===========end of Board 6============')
                    self.printMap()

            if self.args.debug:
                self.printMap()
            print('\n\n----- Clocked Simulation Report -----')
            self.printHeader()
            for p in sorted(players.keys()):
                self.printPersonSummary(p)

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

    def printSummary(self):
        rounds = int(self.args.boards/self.args.bpr)
        numpairs = len(players)
        numtables = int(numpairs/2)
        numcols = rounds + 2  # add in name and totals
        self.hdrRows = numrows = 1 + numtables + 1
        numrows = self.hdrRows + numpairs*2
        self.tab = [['' for i in range(numcols)] for j in range(numrows)]
        self.addHeaderInfo()
        for (pidx, p) in enumerate(sorted(players.keys())):
            self.addPersonInfo(p, pidx)
        calist = ['right']
        for n in range(numcols-2):
            calist.append('center')
        calist.append('right')
        print(tabulate.tabulate(self.tab, tablefmt='plain', colalign=calist))
        
    # header for summaries
    def addHeaderInfo(self):
        self.tab[0][0] = 'Round  |'
        self.tab[0][-1] = 'Totals'
        # for each round put in round number followed by who played who
        for r in range(1, int(self.args.boards/self.args.bpr) + 1):
            self.tab[0][r] = f'    {r:2}     '
            bdnum = (r-1) * self.args.bpr + 1
            rowidx = 1
            for player in map[bdnum].keys():
                tline = map[bdnum][player]
                if tline.origNorth == player:
                    self.tab[rowidx][r] = f'{tline.origNorth[0:3]}-{tline.origEast[0:3]}'
                    rowidx += 1
                    
    def addPersonInfo(self, player, pidx):
        r = self.hdrRows + pidx * 2
        self.tab[r][0] = f'{player:>15}  |  '
        roundMins = 0
        totalPlay = 0
        totalWait = 0
        for bdnum in range(1, self.args.boards+1):
            tline = map[bdnum][player]
            roundMins = roundMins + tline.iElapsed
            waitMins = int(tline.waitMins())
            if bdnum % self.args.bpr == 0:
                col = int(bdnum/self.args.bpr)
                self.tab[r][col] = f'{int(roundMins):02} +{int(waitMins):2}  |  '
                totalPlay = totalPlay + roundMins
                totalWait = totalWait + waitMins
                roundMins = 0
        self.tab[r][-1] = f'  {int(totalPlay):3} + {int(totalWait):2}'
        


class BboTimeTravLine(BboTravLineBase):
    def __init__(self, bdnum, row):
        super(BboTimeTravLine, self).__init__(bdnum, row)
        self.waitEndTime = self.iEndTime  # for end of round records this will be adjusted later

    # for end of round tlines, compute dependenciesx
    def computeWaitEndTime(self, clockedAlg=False):
        deps = {}
        if clockedAlg:
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
    
