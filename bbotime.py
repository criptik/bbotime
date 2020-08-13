from bs4 import BeautifulSoup
import sys
import json
import time
import argparse
import os

global args

map = {}
players = {}
partners = {}
oppositeDir = {'North' : 'South',
               'East' : 'West'}

def parse_args():
    parser = argparse.ArgumentParser(description='BBO Tourney Time Analysis')
    parser.add_argument('--boards', type=int, default=21, help='total number of boards')
    parser.add_argument('--bpr', type=int, default=3, help='boards per round')
    parser.add_argument('--tstart',  help='tournament start date/time')
    parser.add_argument('--dir',  help='directory containing traveler html records')
    
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
        self.waitMins = 0
        self.addStartTime()

    # this thing also handles if a robot came in as a replacement
    def nameForDirection(self, row, dir):
        name = row[dir].lower()
        pard = row[oppositeDir[dir]].lower()
        if name in partners.keys():
            return name
        else:
            # this will return the original partner in this pair
            return partners[pard]
            
        
    def addStartTime(self):
        if self.bdnum == 1:
            self.iStartTime = readTime(args.tstart)
        else:
            prevTravNorth = map['%d-%s' % (self.bdnum-1, self.north)]
            prevTravEast = map['%d-%s' % (self.bdnum-1, self.east)]
            prevNorthEnd =  prevTravNorth.iEndTime
            prevEastEnd =  prevTravEast.iEndTime
            if self.bdnum % args.bpr != 1:
                # use endtime of previous board
                # unless prev board was in a different round
                self.iStartTime = prevNorthEnd
            else:
                # use later of the two previous end times
                self.iStartTime = max(prevNorthEnd, prevEastEnd)
                # and in this case compute wait time for prevTrav for both north and east
                prevTravNorth.waitMins = (self.iStartTime - prevNorthEnd) / 60
                prevTravEast.waitMins = (self.iStartTime - prevEastEnd) / 60
                if False:
                    if self.bdnum == 10 and args.debug:
                        print(self.bdnum, self.north, self.east, self.showtime(prevNorthEnd), self.showtime(prevEastEnd), self.showtime(self.iStartTime))
                        print(prevTravNorth)
                        print(prevTravEast)
                    
                
    def showtime(self, itime):
        return(time.strftime('%H:%M', time.localtime(itime)))

    def elapsed(self):
        return (self.iEndTime - self.iStartTime)/60
        
    def __str__(self):
        mystr = ('N:%15s, E:%15s, Start:%5s, End:%5s, Elapsed:%2d, Wait:%2d' % (self.north, self.east,
                                                                                self.showtime(self.iStartTime),
                                                                                self.showtime(self.iEndTime),
                                                                                self.elapsed(), self.waitMins ))
        return mystr

    
def addToMaps(bdnum, row):
    tline = TravLine(bdnum, row)
    nkey = '%d-%s' % (bdnum, tline.north)
    ekey = '%d-%s' % (bdnum, tline.east)
    map[nkey] = tline
    map[ekey] = tline
    players[tline.north] = 1
    players[tline.east] = 1
    

def printMap():
    for n in range(1, args.boards+1):
        for k in sorted(map.keys()):
            if k.startswith('%d-' % (n)) and map[k].north in k:
                print(n, map[k])
        
# header for summaries
def printHeader():
    print('Round             ', end='')
    for r in range(1, int(args.boards/args.bpr) + 1):
        print('    %2d     ' % (r), end='')
    print('     Totals')

def printPersonSummary(p):
    print()
    print('%15s  |  ' % (p), end = '')
    roundTime = 0
    totalPlay = 0
    totalWait = 0
    for n in range(1, args.boards+1):
        key = '%d-%s' % (n, p)
        tline = map[key]
        roundTime = roundTime + tline.elapsed()
        if n % args.bpr == 0:
            print('%2d +%2d  |  ' % (roundTime, tline.waitMins), end='')
            totalPlay = totalPlay + roundTime
            totalWait = totalWait + tline.waitMins
            roundTime = 0
    print('  %3d + %2d' % (totalPlay, totalWait))

    
def parseFile(n):
    fname1 = '%s/hands (%d).html' % (args.dir, n)
    fname2 = '%s/T%d.html' % (args.dir, n)
    fname = fname1 if os.path.isfile(fname1) else fname2
    file = open(fname)
    html_doc = file.read()

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

    if args.debug:
        print('---- Handling Traveller for Board %d ----' % (n))
        
    # place rows in big table indexed by boardnumber and North
    for row in table_data:
        addToMaps(n, row)


#-------- main stuff starts here -----------
args = parse_args()

for n in range(1, args.boards+1):
    parseFile(n)
    
if args.debug:
    printMap()

printHeader()
for p in sorted(players.keys()):
    printPersonSummary(p)
