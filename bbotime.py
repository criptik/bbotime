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

from bs4 import BeautifulSoup
import sys
import json
import time
import argparse
import os
import itertools
from pprint import pprint

global args

travTableData = []
map = {}
players = {}
partners = {}
opps = {}
oppositeDir = {'North' : 'South',
               'East' : 'West'}

gibName = 'GiB'
robotData = {}

def parse_args():
    parser = argparse.ArgumentParser(description='BBO Tourney Time Analysis')
    # note: we could detect boards per round from the data but support args overrides in case
    # but we do have some built-in defaults for common board counts
    parser.add_argument('--boards', type=int, default=None, help='total number of boards')
    parser.add_argument('--bpr', type=int, default=None, help='boards per round')
    parser.add_argument('--tstart',  default=None, help='tournament start date/time')
    parser.add_argument('--dir',  help='directory containing traveler html records')
    parser.add_argument('--simclocked', default=False, action='store_true', help='afterwards simulate as if clocked had been used')

    parser.add_argument('--robotScores', type=float, nargs='*', default=None, help='supply robot scores to help differentiate between robots which all have the same name') 
    parser.add_argument('--debug', default=False, action='store_true', help='print some debug info') 
    return parser.parse_args()


def readTime(str):
    return time.mktime(time.strptime(str, '%Y-%m-%d %H:%M'))

class TravLine(object):
    def __init__(self, bdnum, row):
        self.bdnum = bdnum
        # record partners if first board
        if bdnum == 1:
            n = row['North'].lower()
            s = row['South'].lower()
            e = row['East'].lower()
            w = row['West'].lower()
            partners[n] = s
            partners[s] = n
            partners[e] = w
            partners[w] = e
        self.iEndTime = readTime(row['Time'])
        self.north = self.nameForDirection(row, 'North')
        self.east = self.nameForDirection(row, 'East')
        self.waitEndTime = self.iEndTime  # for end of round records this will be adjusted later
        self.htmlRow = row   # save in case needed later

    # this thing also handles if a robot came in as a replacement
    def nameForDirection(self, row, dir):
        name = row[dir].lower()
        pard = row[oppositeDir[dir]].lower()
        if name in partners.keys():
            return name
        else:
            # this will return the original partner in this pair
            return partners[pard]

    # for end of round tlines, compute dependenciesx
    def computeWaitEndTime(self, clockedAlg=False):
        deps = {}
        if clockedAlg:
            # just include everyone as a dependency
            for player in map[bdnum].keys():
                deps[player] = 1
        else:
            # normal unclocked logic, compute dependencies
            deps[self.north] = 1
            # find our opp for next round and add that to the deps list
            nextRoundOpp = opps[self.bdnum+1][self.north]
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
            self.iStartTime = readTime(args.tstart)
        else:
            prevTravNorth = map[self.bdnum-1][self.north]
            self.iStartTime = prevTravNorth.waitEndTime

    def waitMins(self):
        return (self.waitEndTime - self.iEndTime) / 60
                
    def showtime(self, itime):
        return(time.strftime('%H:%M', time.localtime(itime)))

    def elapsed(self):
        return (self.iEndTime - self.iStartTime)/60
        
    def __str__(self):
        mystr = ('N:%15s, E:%15s, Start:%5s, End:%5s, Elapsed:%2d, Wait:%2d' % (self.north, self.east,
                                                                                self.showtime(self.iStartTime),
                                                                                self.showtime(self.iEndTime),
                                                                                self.iElapsed, self.waitMins() ))
        return mystr

def initMap():
    for n in range(1, args.boards+1):
        map[n] = {}
        opps[n] = {}
        
        
def addToMaps(bdnum, row):
    tline = TravLine(bdnum, row)
    map[bdnum][tline.north] = tline
    map[bdnum][tline.east] = tline
    players[tline.north] = 1
    players[tline.east] = 1
    opps[bdnum][tline.north] = tline.east
    opps[bdnum][tline.east] = tline.north
    

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
    print(f'  {totalPlay:3} + {totalWait:2}')

    
def parseFile(n):
    # two different naming options supported
    fname1 = f'{args.dir}/hands ({n}).html'
    fname2 = f'{args.dir}/T{n}.html'
    fname = fname1 if os.path.isfile(fname1) else fname2
    file = open(fname)
    html_doc = file.read()

    if args.debug:
        print(f'---- Handling Traveller File {fname} for Board {n} ----')
        

    soup = BeautifulSoup(html_doc, 'html.parser')

    # print(soup.prettify())
    # print(soup.find_all('a')[1]['href'])


    fields = []
    table_data = []
    rows = soup.table.find_all('tr')
    # get rid of rows[0]
    r0 = rows.pop(0)
    if False:
        print(r0)
        print('--------- Rest of Rows -----------')
        print(rows)

    for tr in rows:
        for th in tr.find_all('th', recursive=True):
            thtxt = 'N' if th.text == 'N\u00ba' else th.text
            fields.append(thtxt)
    for tr in rows:
        datum = {}
        for i, td in enumerate(tr.find_all('td', recursive=True)):
            datum[fields[i]] = td.text
        if datum:
            table_data.append(datum)

    # print(json.dumps(table_data, indent=4))
    return table_data

# builds list of tuples of bdnum and table_data (array of trav rows for that bdnum)
def readAllTravFiles():
    for bdnum in range(1, args.boards+1):
        table_data = parseFile(bdnum)
        travTableData.append((bdnum, table_data))

def initRobotData():
    for rndnum in range(1, int(args.boards/args.bpr) + 1):
        robotData[rndnum] = {}
        
                     
def addRobotScores(bdnum, row, dir):
    # robotData will be keyed by roundnum and oppName
    # and the direction which helps if robot is playing robot
    rndnum = int((bdnum-1)/args.bpr) + 1
    oppdir = 'East' if dir == 'North' else 'North'
    key = f'{dir} vs. {row[oppdir].lower()}'
    if robotData[rndnum].get(key) == None:
        robotData[rndnum][key] = []
    # add the score
    fscore = float(row['Score'][:-1])  # strip % sign off end
    if dir == 'East':
        fscore = 100.0 - fscore
    robotData[rndnum][key].append(fscore)
    # print(bdnum, dir, robotData)
    
def buildRobotData(bdnum, row):
    # only do this if one of the two pairs is a robot pair
    for dir in ['North', 'East']:
        if row[dir] == gibName and row[oppositeDir[dir]] == gibName:
            addRobotScores(bdnum, row, dir)

def robKeyOppNamesUnique(keylist):
    oppMap = {}
    for key in keylist:
        oppname = key.split(' vs. ')[1]
        if oppMap.get(oppname) is None:
            oppMap[oppname] = 1
        else:
            return False
    # if we get this far, success
    return True


#-------- main stuff starts here -----------
args = parse_args()
    
# with no explicit boards count, count files in directory
if args.boards is None:
    args.boards = len([name for name in os.listdir(args.dir) if os.path.isfile(os.path.join(args.dir, name))])

# detect defaults for bpr
if args.bpr is None:
    if args.boards == 20:
        args.bpr = 4
    elif args.boards == 21:
        args.bpr = 3

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
readAllTravFiles()

# if robotScores are supplied, use that to try to differentiate between two robot pairs
if args.robotScores is not None:
    initRobotData()
    for (bdnum, table_data) in travTableData:
        for row in table_data:
            buildRobotData(bdnum, row)

    if args.debug:
        print('----- snapshot of robotData ----')
        print(robotData)

    # use itertools to get all the combinations
    keysets = []
    for rndnum in range(1, int(args.boards/args.bpr) + 1):
        keysets.append(list(robotData[rndnum].keys()))
    if args.debug:
        pprint(keysets)

    allCombos = list(itertools.product(*keysets))
    robScoreKeyLists = {}
    for robscore in args.robotScores:
        robScoreKeyLists[robscore] = []
        
    for keylist in allCombos:
        # first make sure all the opponent names are unique across rounds
        # and if so, combine all the scores for all rounds into one list so we can avg it
        if robKeyOppNamesUnique(keylist):    
            rndnum = 1
            scores = []
            for key in keylist:
                scores.extend(robotData[rndnum][key])
                rndnum += 1
            avg = round(sum(scores) / len(scores), 2)
            # pprint(scores)
            # now see if it matches any total robotScores
            for robscore in args.robotScores:
                if avg == robscore:
                    robScoreKeyLists[robscore].append(keylist)

    # now check that each robscore does appear exactly once in the robScoreKeyLists
    # Note: on success need to eventually go back thru travTableData and change GiB names
    for robscore in args.robotScores:
        keylistArray = robScoreKeyLists[robscore]
        if len(keylistArray) == 0:
            print(f'Error: no keylists combos match for robot score {robscore}')
            sys.exit(1)
        print('robscore=', robscore)
        for keylist in keylistArray:
            pprint(keylist)
        if len(keylistArray) > 1:
            print(f'Error: multiple keylists combos match for robot score {robscore}')
            sys.exit(1)

    sys.exit(1)
    
for (bdnum, table_data) in travTableData:
    # place rows in big table indexed by boardnumber and North and East names
    for row in table_data:
        addToMaps(bdnum, row)
    
# With all files processed and in maps, go thru list of TravLine objects
# and compute WaitEndTime (for end of round tlines)
# North and East point to same TravLine object so only need to do one.
for bdnum in range (1, args.boards + 1):
    # note only needed for end of round records and don't need last one
    if bdnum % args.bpr == 0 and bdnum != args.boards:
        for player in map[bdnum].keys():
            tline = map[bdnum][player]
            if player == tline.north:
                tline.computeWaitEndTime()

# now startTimes
for bdnum in range (1, args.boards + 1):
    for player in map[bdnum].keys():
        tline = map[bdnum][player]
        if player == tline.north:
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
                if player == tline.north:            
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
    