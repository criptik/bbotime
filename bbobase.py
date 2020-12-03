from bs4 import BeautifulSoup
import json
import os
import re
import time
import argparse
import tabulate
from abc import ABC, abstractmethod
import csv

from pprint import pprint
import sys
from bborobotfix import BboRobotFixer


class BboBase(object):

    def __init__(self):
        pass

    # the main work routine which reads in the traveler files into travTableData[]
    # and then calls the child to do the rest of the work
    def genReport(self):
        self.parseArguments()
        if self.args.debug:
            print(self.args.__dict__)

        #read all traveler files into travTableData
        self.travTableData = self.readAllTravFiles()
        self.childGenReport()

    # to be overridden
    def childGenReport(self):
        pass

    @classmethod
    def subSuitSym(cls, str):
        useSuitSym = True
        if useSuitSym:
            suitSyms =  {
                'S' : '\N{BLACK SPADE SUIT}',
                'H' : '\N{WHITE HEART SUIT}',
                'D' : '\N{WHITE DIAMOND SUIT}',
                'C' : '\N{BLACK CLUB SUIT}',
            }
            
            for suit in suitSyms.keys():
                str = re.sub(f'{suit}', f'{suitSyms[suit]}', str)
        return str
    

    # builds and returns an array of traveler line objects, one for each row of each board number
    def readAllTravFiles(self):
        travTableData = {}
        # init, array for each bdnum
        for bdnum in range(1, self.args.boards+1):
            travTableData[bdnum] = []
        self.travParser.doParsing(travTableData)
        
        # if robotScores are supplied, use that to try to differentiate between two robot pairs
        if self.args.robotScores is not None:
            BboRobotFixer(self.args, travTableData).robotFix()

        return travTableData

    def determineTravParser(self):
        # for now, look in args.dir for file types
        for f in os.listdir(self.args.dir):
            if f.endswith('.html'):
                return TravParserHtml(self.args)
            elif f.endswith('.csv'):
                return TravParserCsv(self.args)
        # if we got this far, we failed.
        print('--dir directory must contain either .html or .csv files', file=sys.stderr)
        sys.exit(1)
        
    def createObject(self, bdnum, row, travParser):
        return BboTravLineBase(self.args, bdnum, row, travParser)

    def appDescription(self):
        return 'BBO Base'
    
    def parseArguments(self):
        parser = argparse.ArgumentParser(self.appDescription())
        # note: we could detect boards per round from the data but support args overrides in case
        # but we do have some built-in defaults for common board counts
        parser.add_argument('--boards', type=int, default=None, help='total number of boards')
        parser.add_argument('--onlyBoard', type=int, default=None, help='process only this board')
        parser.add_argument('--bpr', type=int, default=None, help='boards per round')
        parser.add_argument('--dir',  help='directory containing traveler html records')
        parser.add_argument('--robotScores', type=float, nargs='*', default=None, help='supply robot scores to help differentiate between robots which all have the same name')
        parser.add_argument('--tablefmt', default='pretty', help='tabulate table format')
        parser.add_argument('--names', nargs="+", help='restrict to travellers with these names')
        parser.add_argument('--avoidUnsafeHtml', default=False, action='store_true', help='set if tabulate unsafehtml tablefmt does not work') 
        parser.add_argument('--playTricksLeftRight', default=False, action='store_true', help='set to get trick order in sequence from left to right') 
        parser.add_argument('--tableBorders', default=False, action='store_true', help='add borders to tables for debugging') 
        parser.add_argument('--debug', default=False, action='store_true', help='print some debug info') 

        # allow child to add args
        self.addParserArgs(parser)
        
        self.args = parser.parse_args()
        # handle some common fixups
        # with no explicit boards count, count files in directory

        self.travParser = self.determineTravParser()
        if self.args.boards is None:
            self.args.boards = self.travParser.getNumBoards()

        # detect defaults for bpr
        if self.args.bpr is None:
            bprMap = {20:4, 21:3, 8:2, 9:3}
            self.args.bpr = bprMap.get(self.args.boards)

    # allow child to add its own args
    def addParserArgs(self, parser):
        pass

    def printHTMLOpening(self):
        borderStyle = '' if not self.args.tableBorders else '''
     table, th, td {
	 border: 1px solid black;
         border-collapse: collapse;
     }
'''
        print('<!doctype html>\n<html><body><pre>')
        print(f'''
        <style>
         .button {{
         background-color: white;
         border: 2px solid black;
	 border-radius: 8px;
         color: black;
         padding: 4px;
         display: inline-block;
	 text-decoration: none;
         }}
        {borderStyle}
        </style>
        ''')
   
    def printHTMLClosing(self):
        print('</pre></body></html>')

    @staticmethod
    def genHtmlTable(tab, args, colalignlist=None, headers=()):
        # in args, we set this false if using some older version of tabulate
        # which doesn't support unsafehtml tablefmt
        if not args.avoidUnsafeHtml:
            tableHtml = tabulate.tabulate(tab, tablefmt='unsafehtml', colalign=colalignlist, headers=headers)
        else:
            # if unsafeHtml doesn't work we have to use html and unescape a bunch of stuff
            tableHtml = tabulate.tabulate(tab, tablefmt='html', colalign=colalignlist)
            tableHtml = self.unescapeInnerHtml(tableHtml)
        # print(tableHtml, file=sys.stderr)
        # doctype html docs don't seem to ignore the multiple whitespace at the end of cells
        # so fix that here, (Maybe there is a way to tell tabulate not to emit those?)
        if True:
            tableHtml = re.sub(' *</td>', '</td>', tableHtml)
            # do that for the header cells also
            tableHtml = re.sub(' *</th>', '</th>', tableHtml)
        return tableHtml

    @staticmethod
    def unescapeInnerHtml(str):
        str = re.sub('&lt;', '<', str)
        str = re.sub('&gt;', '>', str)
        str = re.sub('&quot;', '"', str)
        str = re.sub('&amp;', '&', str)
        str = re.sub('&#x27;', "'", str)
        return str
        

partnerDir = {'North' : 'South',
               'East' : 'West'}

class BboTravLineBase(object):
    @classmethod
    def importArgs(cls, args):
        cls.args = args

    origPartners = {}   # class variable
    def __init__(self, bdnum, row, travParser):
        self.bdnum = bdnum
        self.travParser = travParser
        # row fields mostly handled here but saved in case needed later
        self.row = row  
        self.north = n = self.nameForDirection(row, 'North')
        self.south = s = self.nameForDirection(row, 'South')
        self.east  = e = self.nameForDirection(row, 'East')
        self.west  = w = self.nameForDirection(row, 'West')
        self.playerDir = [self.north, self.east, self.south, self.west]
        if bdnum == 1:
            # record original partners in case a substitution happens later
            self.origPartners[n] = s
            self.origPartners[s] = n
            self.origPartners[e] = w
            self.origPartners[w] = e
        self.origNorth = self.origNameForDirection(row, 'North')
        self.origEast = self.origNameForDirection(row, 'East')

        try:
            self.nsPoints = int(self.travParser.getNSPoints(row))
        except:
            self.nsPoints = None
        self.nsScore  = float(self.travParser.getMPPct(row).rstrip('%'))
        self.linStr = self.travParser.getLinStr(row)
        # parse different parts of result
        resstr = row['Result']
        resstr = re.sub(r'\<.*?\>', '', resstr)
        self.resultStr = resstr
        if self.args.debug:
            print(resstr, len(resstr))
        if resstr.startswith('PASS') or resstr.startswith('A'):
            # special case for passed out or averages
            self.contract = self.dblstr = self.decl = self.trumpstr = None
            self.result = 0
            self.tricks = 0
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
            if suitstr in suitmap.keys():
                suitstr = suitmap[suitstr]
            self.trumpstr = suitstr
            self.contract = f'{level}{suitstr}'
            self.dblstr = dblstr
            self.decl  = decl
            self.result = 0 if result == '=' else int(result)
            self.tricks = int(level) + 6 + self.result
        if self.args.debug:
            pprint(self.__dict__)
            # sys.exit(1)

    # handles gib-gib partnership as special case
    def nameForDirection(self, row, dir):
        name = row[dir].lower()
        if name != 'gib':
            return name
        else:
            return 'gib-ne' if dir in ['North', 'East'] else 'gib-sw'
    
    # this thing also handles if a sub came in as a replacement
    def origNameForDirection(self, row, dir):
        name = self.nameForDirection(row, dir)
        pard = self.nameForDirection(row, partnerDir[dir])
        if name in self.origPartners.keys():
            return name
        else:
            # this will return the original partner in this pair
            # and if doesn't exist in dict, just return name
            return self.origPartners.get(pard, name)  

    # convert time string in traveller to an integer num of secs
    def readTime(self, str):
        return time.mktime(time.strptime(str, '%Y-%m-%d %H:%M'))

    def hasPlayer(self, name):
        return name in self.playerDir

    def checkAndAppend(self, travellers):
        if self.args.names is not None:
            nameMatch = False
            for name in self.args.names:
                if self.hasPlayer(name):
                    nameMatch = True
            if not nameMatch:
                return #without appending
        travellers[self.bdnum].append(self)
        

class Bucket(object):
    def __init__(self):
        self.ary = []

    def count(self):
        return len(self.ary)
    
    def avg(self):
        return round(sum(self.ary) / self.count(), 2)
        
    def show(self, displayName, showCount = True):
        countStr = f'({self.count()})' if showCount else ''
        print(f'{displayName:<35} {self.avg():5.2f}% {countStr}')

    def add(self, score):
        self.ary.append(score)            

    def showCountOnly(self, displayName):
        print(f'{displayName:<35} {self.count()}')


class TravParserBase(ABC):
    def __init__(self, args):
        self.args = args
        self.initParser()

    @abstractmethod
    def initParser(self):
        pass

    @abstractmethod
    def doParsing(self, travTableData):
        pass

    @abstractmethod
    def getLinStr(self, row):
        pass

    @abstractmethod
    def getMPPct(self, row):
        pass

    @abstractmethod
    def getNSPoints(self, row):
        pass

    def getNumBoards(self):
        pass

    def removePercentSyms(self, s):
        # subsitute % symbols
        s = re.sub('%7C', '|', s)
        s = re.sub('%2C', ',', s)
        s = re.sub('%20', ' ', s)
        return s
        
# class to read the html files as pulled over by BBO-2-Brian Helper
class TravParserHtml(TravParserBase):
    def initParser(self):
        pass
    
    def doParsing(self, travTableData):
        for bdnum in range(1, self.args.boards+1):
            table_data = self.parseOneFile(bdnum)
            for row in table_data:
                travTableData[bdnum].append(row)                    

    def getLinStr(self, row):
        s = row['LinStr']
        s = self.removePercentSyms(s)
        # everything before pn goes
        s = re.sub('^.*?pn\|', '|pn|', s)
        # get rid of single quotes
        s = re.sub("'", "", s)
        # get rid of end
        s = re.sub('\);this.*?$', '', s)
        return s
    
    def getMPPct(self, row):
        return row['Score']

    def getNSPoints(self, row):
        return row['NS Points']

    def getNumBoards(self):
        # html directories have one file per board
        return len([name for name in os.listdir(self.args.dir) if os.path.isfile(os.path.join(self.args.dir, name)) and name.endswith('.html')])
    
    # this routine reads the html file for one traveller and uses BeautifulSoup
    # to return an array of rows, each a dict for a single row of the html file
    def parseOneFile(self, n):
        # two different naming options supported
        fname1 = f'{self.args.dir}/hands ({n}).html'
        fname2 = f'{self.args.dir}/T{n}.html'
        fname = fname1 if os.path.isfile(fname1) else fname2
        try:
            file = open(fname)
        except Exception as ex:
            print(f'Error: cannot find {fname1} or {fname2}', file=sys.stderr)
            sys.exit(1)
        html_doc = file.read()

        if self.args.debug:
            print(f'---- Handling Traveller File {fname} for Board {n} ----')


        soup = BeautifulSoup(html_doc, 'html.parser')

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
            #build fields array
            for th in tr.find_all('th', recursive=True):
                fields.append(th.text)
        for tr in rows:
            datum = {}
            for i, td in enumerate(tr.find_all('td', recursive=True)):
                # skip some useless fields
                if fields[i] not in ['N\u00ba', 'Movie']:
                    datum[fields[i]] = td.text
                #special case for Movie element (lin info encoded in onclick)
                if fields[i] == 'Movie':
                    datum['LinStr'] = td.find('a').attrs['onclick']
            if datum:
                table_data.append(datum)

        # print(json.dumps(table_data, indent=4))
        return table_data

# class to read the csv file as created by BBO Extractor
class TravParserCsv(TravParserBase):
    def initParser(self):
        pass

    def getLinStr(self, row):
        s = row['playdata']
        # print(s)
        return self.removePercentSyms(s)

    def getMPPct(self, row):
        return row['Percent']

    def getNSPoints(self, row):
        return row['Score']

    def getNumBoards(self):
        # csv directories have one .csv file
        # look in that for a #Boards line
        fname = self.getCsvFileName()
        with open(fname, 'r') as read_obj:
            print(read_obj)
            line = next(read_obj).rstrip()
            while line:
                print(line)
                fields = line.split(',')
                if fields[0] == '#BoardCount':
                    return int(fields[1])
                line = next(read_obj).rstrip()
        return None

    def getCsvFileName(self):
        fname = None
        for fn in os.listdir(self.args.dir):
            if fn.endswith('.csv'):
                return f'{self.args.dir}/{fn}'
        return None
    
    def doParsing(self, travTableData):
        fname = self.getCsvFileName()    
        with open(fname, 'r') as read_obj:
            found = False
            travlines = []
            while True:
                line = next(read_obj).rstrip()
                # print(line)
                if found:
                    travlines.append(line.lstrip('#'))
                if line == '#TravellerLines':
                    print('start appending next line')
                    found = True
                if found and (line == '' or line == '#Substitutions'):
                    print('stop appending')
                    break

        print('last line is', travlines[-1])
        # now travlines can be read by csvreader
        csv_reader = csv.DictReader(travlines)
        # Iterate over each row after the header in the csv
        for row in csv_reader:
            # row variable is a dict that represents a row in csv
            # pprint(row)
            bdnum = int(row['Board'])
            if bdnum > self.args.boards:
                break
            else:
                row['Time'] = None  #kludge
                travTableData[bdnum].append(row)
            
        
