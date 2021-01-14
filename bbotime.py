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
import re
from abc import ABC, abstractmethod

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
        parser.add_argument('--minsPerBoard', default=6, type=int, help='minutes allowed per board (for simclocked)')
        parser.add_argument('--showTimeline', default=False, action='store_true', help='use grid to show timelines')

    def childArgsFix(self):
        # build default start time from directory name (if start time not supplied in args)
        if self.args.tstart is None:
            head, sep, tail = self.args.dir.partition('/')
            if head == 'travs':
                self.args.tstart = tail + ' 15:00'


    def childStyleInfo(self):
        return (GridGen.styleInfo() if self.args.showTimeline else '')
        
    def childGenReport(self):
        # check whether these datafiles support the time field which we need
        if not self.supportsTimeField():
            print(f'ERROR: The data files in {self.args.dir} do not support the Time Field, which we need', file=sys.stderr)
            sys.exit(1)
            
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

        summaryGen = TableSummaryGen(self.args) if not self.args.showTimeline else GridSummaryGen(self.args)
        
        self.printHTMLOpening()
        summaryGen.printSummary(f'\nUnclocked Report for {self.args.tstart}')
        
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
            summaryGen.printSummary(f'\n\nClocked Simulation for {self.args.tstart} with {self.args.minsPerBoard} minutes per board')

        self.printHTMLClosing()

    def initMap(self):
        for n in range(1, self.args.boards+1):
            map[n] = {}
            opps[n] = {}


    def addToMaps(self, bdnum, row):
        tline = BboTimeTravLine(bdnum, row, self.travParser)
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


class SummaryGenBase(ABC):
    def __init__(self, args):
        self.args = args
        self.numpairs = len(players)
        self.rounds = int(self.args.boards/self.args.bpr)
        
    def printSummary(self, title):
        print(title)
        self.setupSummary()
        self.addHeaderInfo()
        self.buildColorDicts()
        for (pidx, p) in enumerate(sorted(players.keys())):
            self.addPersonInfo(p, pidx)
        print(self.renderSummary())
        
    def buildColorDicts(self):
        # for each round figure out colors
        self.colorDicts = []
        for rnd in range(1, self.rounds + 1):
            bdnum = (rnd-1) * self.args.bpr + 1
            thisColorDict = {}
            colors = ['cyan', 'pink', 'lightgreen', 'yellow', 'plum', 'orange']
            colorIndex = 0
            for player in map[bdnum].keys():
                tline = map[bdnum][player]
                if player not in thisColorDict.keys():
                    thisColorDict[tline.origNorth] = thisColorDict[tline.origEast] = colors[colorIndex]
                    colorIndex += 1
            self.colorDicts.append(thisColorDict)
        
    def addPersonInfo(self, player, pidx):
        totalPlay = 0
        totalWait = 0
        maxWait = 0
        for rnd in range(1, self.rounds + 1):
            roundMins = self.roundElapsedMins(rnd, player)
            tlineLastInRound = map[rnd * self.args.bpr][player]
            waitMins = tlineLastInRound.waitMins()
            myColor = self.colorDicts[rnd-1][player]
            self.putPlayerRoundInfo(player, pidx, rnd, roundMins, waitMins, tlineLastInRound, myColor)
            totalPlay += roundMins
            totalWait += waitMins
            maxWait = max(maxWait, waitMins)

        self.addPairNameAndTotals(pidx, player, totalPlay, totalWait, maxWait)
        
    # return elapsedTime and waitTime for that round for a given player
    def roundElapsedMins(self, rnd, player):
        bdnumLastInRound = rnd * self.args.bpr
        bdnumFirstInRound = bdnumLastInRound - self.args.bpr + 1
        return int((map[bdnumLastInRound][player].iEndTime - map[bdnumFirstInRound][player].iStartTime) / 60)

    @abstractmethod
    def putPlayerRoundInfo(self, player, pidx, rnd, roundMins, waitMins, tlineLastInRound, myColor):
        pass
    
    def fixHtml(self, tableHtml):
        return tableHtml
    
    @abstractmethod    
    def setupSummary(self):
        pass

    @abstractmethod    
    def renderSummary(self):
        pass

    @abstractmethod    
    def addHeaderInfo(self):
        pass

    @abstractmethod    
    def addPairNameAndTotals(self, pidx, player, totalPlay, totalWait, maxWait):
        pass
    
class TableSummaryGen(SummaryGenBase):
    def setupSummary(self):
        self.numcols = self.rounds + 3  # add in name and totals and max
        self.hdrRows = 1
        numrows = self.hdrRows + self.numpairs * self.args.rowsPerPlayer
        self.tab = [['' for i in range(self.numcols)] for j in range(numrows)]

    # header for summaries
    def addHeaderInfo(self):
        self.tab[0][0] = 'Round->'
        self.tab[0][-2] = '---Totals---'
        self.tab[0][-1] = '-Max Wait-'
        # for each round put in round number
        for rnd in range(1, self.rounds + 1):
            self.tab[0][rnd] = f'{rnd:2}'
        
    def renderSummary(self):
        calist = []
        for n in range(self.numcols):
            calist.append('center')
        calist[0] = calist[-2] = calist[-1] = 'right'
        tableHtml = BboBase.genHtmlTable(self.tab, self.args, colalignlist=calist)
        # do any fixups required
        tableHtml = self.fixHtml(tableHtml)
        return tableHtml
        
    def fixHtml(self, tableHtml):
        # must go thru and move the background-color things into the td elements
        tableHtml = re.sub('<td style="(.+?)"> *(background-color:\w+) (.+?)</td>',
                           r'<td style="\1 \2;">\3</td>',
                           tableHtml)
        # the "header" row had weird spacing, fix that
        tableHtml = re.sub('> {6,}(\d+)</td>',
                           r'>     \1     </td>',
                           tableHtml)
        
        return tableHtml

    def putPlayerRoundInfo(self, player, pidx, rnd, roundMins, waitMins, tlineLastInRound, myColor):
        row = self.hdrRows + pidx * self.args.rowsPerPlayer
        col = rnd
        specialChar = ' ' if not tlineLastInRound.clockedTruncation else '*'
        # add a background-color in the cell data which will later be moved into the <td> element
        # this works better than using span
        self.tab[row][col] = f'background-color:{myColor} {int(roundMins):2}{specialChar}+{int(waitMins):2}'

    def addPairNameAndTotals(self, pidx, player, totalPlay, totalWait, maxWait):
        row = self.hdrRows + pidx * self.args.rowsPerPlayer
        self.tab[row][0] = player
        self.tab[row][-2] = f'  {int(totalPlay):3} + {int(totalWait):2}'
        self.tab[row][-1] = f'{int(maxWait):2}'

        
class GridSummaryGen(SummaryGenBase):

    def setupSummary(self):
        # compute total number of minutes for tournament
        tournElapsedMins = int(self.getElapsedMins(1, self.rounds))
        self.gridGen = GridGen(tournElapsedMins)
        print(self.gridGen.gridOpen())
        # data structs that will hold playerRoundInfo
        self.roundTuples = {}
        for p in players.keys():
            self.roundTuples[p] = []
        
    def getElapsedMins(self, startRound, endRound):
        iStartTimes = []
        iEndTimes = []
        startBoard = ((startRound - 1) * self.args.bpr) + 1
        endBoard = endRound * self.args.bpr
        # get min start
        for player in map[startBoard].keys():
            tline = map[startBoard][player]
            iStartTimes.append(tline.iStartTime)
        miniStartTime = min(iStartTimes)
        
        # get max end
        for player in map[self.args.boards].keys():
            tline = map[self.args.boards][player]
            iEndTimes.append(tline.iEndTime)
        maxiEndTime = max(iEndTimes)
        elapsedMins = int(maxiEndTime - miniStartTime)/60
        if False:
            print(iEndTimes)
            print(maxiEndTime, miniStartTime)
            print(elapsedMins)
        return elapsedMins
            
        
    def putPlayerRoundInfo(self, player, pidx, rnd, roundMins, waitMins, tlineLastInRound, myColor):
        specialChar = ' ' if not tlineLastInRound.clockedTruncation else '*'
        # append a 3-tuple for this player
        self.roundTuples[player].append((myColor, roundMins, waitMins))
        
    def renderSummary(self):
        pass

    # header for summaries
    def addHeaderInfo(self):
        # for now, nothing.  Maybe later
        pass

    def addPairNameAndTotals(self, pidx, player, totalPlay, totalWait, maxWait):
        # when this is called, all RoundTuples for this player are complete
        # so we can call gridGen to do a row
        if False:
            print(player, self.roundTuples[player])
            sys.exit(1)
        rowHtml = self.gridGen.gridRow(player, self.roundTuples[player], f'{int(totalPlay):3} + {int(totalWait):2}', maxWait)
        print(rowHtml)
    

class GridGen(object):
    def __init__(self, rowTime):
        self.rowTime = rowTime
        self.rowNum = 1

    @classmethod
    def styleInfo(cls):
        return '''
	.grid-container {
	     display: grid;
	     grid-gap: 1px;
	     padding: 2px;
	     background-color: grey;
	 }

	 .grid-container > div {
	     text-align: center;
	     padding-top: 5px;
	     padding-bottom: 5px;
	     font-size: 15px;
             max-height: 25px;
	 }

         .divtext {
             background-color: white;
             white-space: nowrap;
             padding-left: 5px;
             padding-right: 5px
          }
        '''

    def gridOpen(self):
        # +3 here because of name, tot, max columns
        colTemplate = f'repeat({3 + self.rowTime}, 1fr)'
        return self.divOpen('grid-container', {'grid-template-columns': colTemplate, 'width' : '1500px'})

    def gridRow(self, pairName, roundTuples, totsStr, max):
        # basically checks the roundTuples meets rowTime
        totalTime = 0
        colorSpans = []
        for (color, playTime, waitTime) in roundTuples:
            colorSpans.append((color, playTime))
            colorSpans.append(('white', waitTime))
            totalTime += (playTime + waitTime)
        if totalTime != self.rowTime:
            print(f'row {self.rowNum}, roundTuples does not add up to {self.rowTime}: {roundTuples}', file=sys.stderr)
            if totalTime <= self.rowTime:
                waitDelta = self.rowTime - totalTime
                print(f'adding waitTime of {waitDelta} at the end', file=sys.stderr)
                (color, oldWaitTime) = colorSpans.pop()
                colorSpans.append((color, oldWaitTime + waitDelta))
            else:
                # greater than, no fixup possible
                print(f'Fatal', file=sys.stderr)
                sys.exit(1)
        self.rowNum += 1
        return self.fullRowHtml(pairName, colorSpans, totsStr, max)

    @staticmethod
    def attrStr(attr, val):
        return f'{attr}="{val}"'

    @staticmethod
    def divOpen(cls=None, styles=None, finalcr=True):
        classStr =  styleStr = ''
        if cls is not None:
            classStr = GridGen.attrStr('class', cls)
        if styles is not None:
            stylist = ''
            for sty in styles.keys():
                stylist += f'{sty}:{styles[sty]}; '
            styleStr = GridGen.attrStr('style', stylist)
        divStr = f'<div {classStr} {styleStr}>'
        if finalcr:
            divStr += '\n'
        return divStr

    @staticmethod
    def divClose():
        return '</div>'

    @staticmethod
    def divFull(cls=None, styles=None, content=''):
        return f'{GridGen.divOpen(cls, styles, False)}{content}{GridGen.divClose()}\n'


    @staticmethod
    def textCellDiv(content):
        styles={}
        styles['grid-column-end'] = 'span 1'
        return GridGen.divFull('divtext', styles, content)

    @staticmethod
    def fullRowHtml(pairName, colorSpans, tots, max):
        nameCellStyles = {
            'grid-area': ' / 1 / / span 1',
        }
        s = ''
        s += GridGen.divFull('divtext', nameCellStyles, pairName)
        for (color, spanAmt) in colorSpans:
            if spanAmt == 0:
                continue
            styles = {}
            styles['background-color'] = color
            styles['grid-column-end'] = f'span {spanAmt}'
            s += GridGen.divFull(None, styles, f'{spanAmt}')
        for content in [tots, max]:
            s += GridGen.textCellDiv(content)
        return s + '\n'


class BboTimeTravLine(BboTravLineBase):
    def __init__(self, bdnum, row, travParser):
        super(BboTimeTravLine, self).__init__(bdnum, row, travParser)
        self.iEndTime = self.readTime(self.row['Time'])
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
        return int((self.waitEndTime - self.iEndTime) / 60)
                
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
if __name__ == '__main__':
    BboTimeReporter().genReport()
    
