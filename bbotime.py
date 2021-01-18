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
noPlays = {}

class BboTimeReporter(BboBase):
    def appDescription(self):
        return 'BBO Tourney Time Analysis'

    def addParserArgs(self, parser):
        parser.add_argument('--tstart',  default=None, help='tournament start date/time')
        parser.add_argument('--simclocked', default=False, action='store_true', help='afterwards simulate as if clocked had been used')
        parser.add_argument('--rowsPerPlayer', default=1, type=int, help='rows per player in table')
        parser.add_argument('--minsPerBoard', default=6, type=int, help='minutes allowed per board (for simclocked)')
        parser.add_argument('--showTimeline', default=False, action='store_true', help='use grid to show timelines')
        parser.add_argument('--noRoundLabels', default=False, action='store_true', help='avoid round labels in timeline')
        parser.add_argument('--incLastRoundWait', default=False, action='store_true', help='include last round waiting in totals and max')

    def childArgsFix(self):
        # build default start time from directory name (if start time not supplied in args)
        if self.args.tstart is None:
            head, sep, tail = self.args.dir.partition('/')
            if head == 'travs':
                self.args.tstart = tail + ' 15:00'


    def childStyleInfo(self):
        return (GridGenBase.styleInfo())

    def noPlaysInit(self):
        for player in players:
            noPlays[player] = set()
            
    def noPlaysAdd(self, player, bdnum):
        noPlays[player].add(bdnum)

    def tournDesc(self):
        rounds = int(self.args.boards/self.args.bpr)
        return f'{self.args.tstart}, {self.args.boards} Boards, {rounds} Rounds of {self.args.bpr}' 

    def createSummaryGen(self):
        return FixedWidthGridSummaryGen(self.args) if not self.args.showTimeline else TimelineGridSummaryGen(self.args)

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

        self.noPlaysInit()

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
        # and while we're at it, count noplays
        for bdnum in range (1, self.args.boards + 1):
            for player in map[bdnum].keys():
                tline = map[bdnum][player]
                if player == tline.origNorth:
                    tline.addStartTime()
                    tline.iElapsed = tline.elapsed()
                if tline.isNoPlay:
                    self.noPlaysAdd(player, bdnum)

        if self.args.debug:
            self.printMap()

        summaryGen = self.createSummaryGen()
        
        self.printHTMLOpening()
        summaryGen.printSummary(f'\nUnclocked Report for {self.tournDesc()}')
        
        if self.args.simclocked:
            self.noPlaysInit()
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
                        self.noPlaysAdd(player, bdnum)
                        # also add the opponent since we won't come thru here for them
                        self.noPlaysAdd(opps[bdnum][player], bdnum)
                        
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

                if False and bdnum == self.args.boards:
                    for player in players:
                        if len(noPlays[player]) > 0:
                            print(player, noPlays[player], file=sys.stderr)
                    
            if self.args.debug:
                self.printMap()
            # get a new summaryGen because total tourney time might have changed
            summaryGen = self.createSummaryGen()
            summaryGen.printSummary(f'\n\nClocked Simulation for {self.tournDesc()}, with {self.args.minsPerBoard} minutes per board time limit')

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
        self.tournElapsedMins = int(self.getElapsedMins(1, self.rounds))
        
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
            totalPlay += roundMins
            totalWait += waitMins
            myColor = self.colorDicts[rnd-1][player]
            # if last round, check totals and increase last wait if needed
            # for now, we don't want to include this extra time in totalWait or maxWait
            if self.args.incLastRoundWait and rnd == self.rounds and (totalPlay + totalWait) < self.tournElapsedMins:
                waitDelta = self.tournElapsedMins - (totalPlay + totalWait)
                waitMins += waitDelta
                totalWait += waitDelta
            maxWait = max(maxWait, waitMins)
            self.putPlayerRoundInfo(player, pidx, rnd, roundMins, waitMins, tlineLastInRound, myColor)

        self.addPairNameAndTotals(pidx, player, totalPlay, totalWait, maxWait, len(noPlays[player]))
        
    # return elapsedTime and waitTime for that round for a given player
    def roundElapsedMins(self, rnd, player):
        bdnumLastInRound = rnd * self.args.bpr
        bdnumFirstInRound = bdnumLastInRound - self.args.bpr + 1
        return int((map[bdnumLastInRound][player].iEndTime - map[bdnumFirstInRound][player].iStartTime) / 60)

    # used to get total length of tournament
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
    def addPairNameAndTotals(self, pidx, player, totalPlay, totalWait, maxWait, numNoPlays):
        pass

# the original gen using html tables (only works for non-timeline view)
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

    def addPairNameAndTotals(self, pidx, player, totalPlay, totalWait, maxWait, numNoPlays):
        row = self.hdrRows + pidx * self.args.rowsPerPlayer
        self.tab[row][0] = player
        self.tab[row][-2] = f'  {int(totalPlay):3} + {int(totalWait):2}'
        self.tab[row][-1] = f'{int(maxWait):2}'

# base class for grid generation summaries (timeline and no-timeline_        
class GridSummaryGenBase(SummaryGenBase):

    def setupSummary(self):
        # compute total number of minutes for tournament
        self.gridGen = self.createGridGen()
        self.html = ''
        self.html += self.gridGen.gridOpen()
        # data structs that will hold playerRoundInfo
        self.roundTuples = {}
        for p in players.keys():
            self.roundTuples[p] = []
        
        
    def putPlayerRoundInfo(self, player, pidx, rnd, roundMins, waitMins, tlineLastInRound, myColor):
        specialChar = ' ' if not tlineLastInRound.clockedTruncation else '*'
        # append a 4-tuple for this player
        self.roundTuples[player].append((myColor, roundMins, waitMins, specialChar))
        
    def renderSummary(self):
        self.html += self.gridGen.gridClose()
        return(self.html)

    # header for summaries
    def addHeaderInfo(self):
        # for now, nothing.  Maybe later
        pass

    def addPairNameAndTotals(self, pidx, player, totalPlay, totalWait, maxWait, numNoPlays):
        # when this is called, all RoundTuples for this player are complete
        # so we can call gridGen to do a row
        if False:
            print(player, self.roundTuples[player])
            sys.exit(1)
        addLabels = not self.args.noRoundLabels
        rowHtml = self.gridGen.gridRow(player, self.roundTuples[player], f'{int(totalPlay):3} + {int(totalWait):2}', maxWait, numNoPlays, addLabels)
        self.html += rowHtml

    @abstractmethod
    def createGridGen(self):
        pass


class TimelineGridSummaryGen(GridSummaryGenBase):
    def createGridGen(self):
        return TimelineGridGen(self.args, self.tournElapsedMins)        


class FixedWidthGridSummaryGen(GridSummaryGenBase):
    def createGridGen(self):
        return FixedWidthGridGen(self.args, self.tournElapsedMins)        


class GridGenBase(ABC):
    def __init__(self, args, rowTime):
        self.args = args
        self.rowTime = rowTime
        self.rowNum = 1
        self.rounds = int(self.args.boards/self.args.bpr)

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
	 }

         .divtext {
             background-color: white;
             white-space: nowrap;
             padding-left: 5px;
             padding-right: 5px
          }
     .grid-container .roundnum {
         background-color: wheat;
	 padding: 0px 0px 0px 0px;
	 font-size: 10px;
	 grid-row-start : auto;
	 grid-column-start : auto;
	 grid-row-end : auto;
     }
     .grid-container .round1 {
	 grid-column-start : 2;
     }

        '''

    def gridOpen(self):
        # +4 here because of name, tot, max, numNoPlays columns
        colTemplate = self.getColTemplate()
        return self.divOpen('grid-container', {'grid-template-columns': colTemplate, 'width' : '1500px'})

    @abstractmethod
    def getColTemplate(self):
        pass
    
    def gridClose(self):
        return self.divClose()

    @abstractmethod
    def gridRow(self, pairName, roundTuples, totsStr, max, numNoPlays, addLabels=True):
        pass
    

    def attrStr(self, attr, val):
        return f'{attr}="{val}"'

    def divOpen(self, divcls=None, styles=None, finalcr=True):
        classStr =  styleStr = ''
        if divcls is not None:
            classStr = self.attrStr('class', divcls)
        if styles is not None:
            stylist = ''
            for sty in styles.keys():
                stylist += f'{sty}:{styles[sty]}; '
            styleStr = self.attrStr('style', stylist)
        divStr = f'<div {classStr} {styleStr}>'
        if finalcr:
            divStr += '\n'
        return divStr

    def divClose(self):
        return '</div>'

    def divFull(self, divcls=None, styles=None, content=''):
        return f'{self.divOpen(divcls, styles, False)}{content}{self.divClose()}\n'


    def textCellDiv(self, content):
        styles={}
        styles['grid-column-end'] = 'span 1'
        return self.divFull('divtext', styles, content)

    def fullRowHtml(self, pairName, colorSpans, roundSpans, tots, max, numNoPlays):
        nameRowSpan = 2 if roundSpans is not None else 1
        nameCellStyles = {
            'grid-area': f' auto / 1 / span {nameRowSpan} / span 1',
        }
        s = ''
        s += self.divFull('divtext', nameCellStyles, pairName)
        # do the round Labels if specified
        if roundSpans is not None:
            for (rndidx, roundSpan) in enumerate(roundSpans):
                cls = 'roundnum round1' if rndidx == 0 else 'roundnum'
                s += self.divFull('roundnum', {'grid-column-end' : f'span {roundSpan}'}, f'R{rndidx+1}')
            # tots and max labels
            s += self.divFull('roundnum', {'grid-column-end' : f'span 1'}, 'Totals')
            s += self.divFull('roundnum', {'grid-column-end' : f'span 1'}, 'Max')
            s += self.divFull('roundnum', {'grid-column-end' : f'span 1'}, 'NP')

        for (color, spanAmt, content) in colorSpans:
            if spanAmt == 0:
                continue
            styles = {}
            styles['background-color'] = color
            styles['grid-column-end'] = f'span {spanAmt}'
            s += self.divFull(None, styles, content)
        # fill in the rightmost cols
        for content in [tots, max, numNoPlays]:
            s += self.textCellDiv(content)
        return s + '\n'

# class which uses Grid to create a timeline
class TimelineGridGen(GridGenBase):
    def getColTemplate(self):
        colTemplate = f'repeat({4 + self.rowTime}, 1fr)'
        return colTemplate
    
    def gridRow(self, pairName, roundTuples, totsStr, max, numNoPlays, addLabels=True):
        # create the colorspans and also check the roundTuples meets rowTime
        totalTime = 0
        colorSpans = []
        roundSpans = []
        for (color, playTime, waitTime, specialChar) in roundTuples:
            if specialChar == ' ':
                specialChar = ''
            content = f'{playTime}{specialChar}'
            colorSpans.append((color, playTime, content))
            colorSpans.append(('white', waitTime, f'{waitTime}'))
            roundTime = playTime + waitTime
            roundSpans.append(roundTime)
            totalTime += roundTime
        if totalTime != self.rowTime:
            if self.args.debug or totalTime > self.rowTime:
                print(f'row {self.rowNum}, roundTuples does not add up to {self.rowTime}: {roundTuples}', file=sys.stderr)
            if totalTime <= self.rowTime:
                waitDelta = self.rowTime - totalTime
                if self.args.debug:
                    print(f'adding waitTime of {waitDelta} at the end', file=sys.stderr)
                (color, oldWaitTime, oldContent) = colorSpans.pop()
                newWaitTime = oldWaitTime + waitDelta
                colorSpans.append((color, newWaitTime, f'{newWaitTime}'))
                # do similarly for roundSpans
                oldRoundSpan = roundSpans.pop()
                roundSpans.append(oldRoundSpan + waitDelta)
            else:
                # greater than, no fixup possible
                print(f'Fatal', file=sys.stderr)
                sys.exit(1)
        self.rowNum += 1
        if not addLabels:
            roundSpans = None
        return self.fullRowHtml(pairName, colorSpans, roundSpans, totsStr, max, numNoPlays)


# class which uses Grid to create a non-timeline view
class FixedWidthGridGen(GridGenBase):
    def getFixedRoundSpan(self):
        return 3

    def getColTemplate(self):
        colTemplate = f'repeat({4 + (self.rounds * self.getFixedRoundSpan())}, 1fr)'
        return colTemplate

    def gridRow(self, pairName, roundTuples, totsStr, max, numNoPlays, addLabels=True):
        # create the colorspans and also check the roundTuples meets rowTime
        totalTime = 0
        colorSpans = []
        roundSpans = []
        for (color, playTime, waitTime, specialChar) in roundTuples:
            if specialChar == ' ':
                specialChar = ''
            content = f'{playTime}{specialChar} + {waitTime}'
            colorSpans.append((color, self.getFixedRoundSpan(), content))
        if not addLabels or self.rowNum > 1:
            roundSpans = None
        else:
            # each roundspan in no-timeline mode is span 1
            for roundnum in range(1, self.rounds+1):
                roundSpans.append(self.getFixedRoundSpan())

        self.rowNum += 1
        return self.fullRowHtml(pairName, colorSpans, roundSpans, totsStr, max, numNoPlays)
    
# traveller line specialization for bbotime
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
    
