from bs4 import BeautifulSoup
import json
import os
import re
import time
from pprint import pprint
import sys
from bborobotfix import BboRobotFixer

class BboParserBase(object):

    def __init__(self, args):
        self.args = args
    

    # this routine reads the html file for one traveller and uses BeautifulSoup
    # to return an array of rows, each a dict for a single row of the html file
    def parseFile(self, n):
        # two different naming options supported
        fname1 = f'{self.args.dir}/hands ({n}).html'
        fname2 = f'{self.args.dir}/T{n}.html'
        fname = fname1 if os.path.isfile(fname1) else fname2
        file = open(fname)
        html_doc = file.read()

        if self.args.debug:
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

    # builds and returns an array of traveler line objects, one for each row of each board number
    def readAllTravFiles(self):
        travTableData = {}
        # init, array for each bdnum
        for bdnum in range(1, self.args.boards+1):
            travTableData[bdnum] = []

        for bdnum in range(1, self.args.boards+1):
            table_data = self.parseFile(bdnum)
            for row in table_data:
                if False:
                    obj = self.createObject(bdnum, row)
                    travTableData[bdnum].append(obj)
                else:
                    travTableData[bdnum].append(row)                    

        # if robotScores are supplied, use that to try to differentiate between two robot pairs
        if self.args.robotScores is not None:
            BboRobotFixer(self.args, travTableData).robotFix()

        return travTableData

    def createObject(self, bdnum, row):
        return BboTravLineBase(self.args, bdnum, row)

                                    
partnerDir = {'North' : 'South',
               'East' : 'West'}

class BboTravLineBase(object):
    origPartners = {}   # class variable
    def __init__(self, args, bdnum, row):
        self.args = args
        self.bdnum = bdnum
        self.north = n = row['North'].lower()
        self.south = s = row['South'].lower()
        self.east  = e = row['East'].lower()
        self.west  = w = row['West'].lower()
        if bdnum == 1:
            # record original partners in case a substitution happens later
            self.origPartners[n] = s
            self.origPartners[s] = n
            self.origPartners[e] = w
            self.origPartners[w] = e
        self.origNorth = self.origNameForDirection(row, 'North')
        self.origEast = self.origNameForDirection(row, 'East')

        self.nsPoints = row['NS Points']
        self.nsScore  = row['Score']
        self.iEndTime = self.readTime(row['Time'])
        # parse different parts of result
        resstr = row['Result']
        resstr = re.sub(r'\<.*?\>', '', resstr)
        if args.debug:
            print(resstr, len(resstr))
        if resstr.startswith('PASS') or resstr.startswith('A'):
            # special case for passed out or averages
            self.contract = None
            self.dblstr = None
            self.decl  = None
            self.result = 0
        else:
            # normal (not passed out) hands
            m = re.search(r'([0-9])(.*?)(x{0,2})([NSEW])(=|\+[0-9]*|\-[0-9]*)', resstr)
            if m is None:
                print(f'Could Not Parse "{resstr}"')
                sys.exit(1)
            (level, suitstr, dblstr, decl, result) = m.groups()
            suitstr = suitstr.lstrip('&')
            # print(level, suitstr, dblstr, decl, result)
            # translate suitstr
            suitmap = {'\N{BLACK SPADE SUIT}' : 'S',
                       '\N{BLACK HEART SUIT}' : 'H',
                       '\N{BLACK DIAMOND SUIT}' :  'D',
                       '\N{BLACK CLUB SUIT}' :  'C',
                       'N'       :  'N' }
            suitstr = suitmap[suitstr]
            self.contract = f'{level}{suitstr}'
            self.dblstr = dblstr
            self.decl  = decl
            self.result = 0 if result == '=' else int(result)
        if self.args.debug:
            pprint(self.__dict__)
            # sys.exit(1)

    # this thing also handles if a sub came in as a replacement
    def origNameForDirection(self, row, dir):
        name = row[dir].lower()
        pard = row[partnerDir[dir]].lower()
        if name in self.origPartners.keys():
            return name
        else:
            # this will return the original partner in this pair
            return self.origPartners[pard]

    # convert time string in traveller to an integer num of secs
    def readTime(self, str):
        return time.mktime(time.strptime(str, '%Y-%m-%d %H:%M'))
