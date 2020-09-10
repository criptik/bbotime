import sys
import time
import os
import collections
import sys
import time
import os
import collections
from pprint import pprint

from bboparse import BboParserBase, BboTravLineBase

global args

travTableData = []
map = {}
players = {}
partners = {}
opps = {}

class BboDefOffParser(BboParserBase):
    def appDescription(self):
        return 'BBO Tourney Defense/Offense Analysis'

    def addParserArgs(self, parser):
        pass
    
class BboDefOffTravLine(BboTravLineBase):
    def __init__(self, bdnum, row):
        super(BboDefOffTravLine, self).__init__(bdnum, row)
        self.playerDir = [self.north, self.east, self.south, self.west]


def nested_dict():
    return collections.defaultdict(nested_dict)

bucketTable = nested_dict()
vsOppTable = nested_dict()

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


# sorting key routines
# def vsScore(bucketName):
#     return bigTable

#-------- main stuff starts here -----------

myBboParser = BboDefOffParser()
args = myBboParser.parseArguments()
if args.debug:
    print(args.__dict__)

travTableData = []
#read all traveler files into travTableData
travTableData = myBboParser.readAllTravFiles()

bucketNameMap = [
    ['OffDecl',    'Offense All'],      # 0
    ['DefNotLead', 'Defense All'],      # 1
    ['OffDummy',   'Offense All'],      # 2
    ['DefLead',    'Defense All'],      # 3
]

BboDefOffTravLine.importArgs(args)
for bdnum in range (1, args.boards + 1):
    for row in travTableData[bdnum]:
        tline = BboDefOffTravLine(bdnum, row)
        # print(f'bdnum={bdnum}')
        # pprint(tline.__dict__)
        # for now, we really only need North and East
        for player in tline.playerDir[:2]:
            playerIdx = tline.playerDir.index(player)
            score = tline.nsScore if playerIdx in [0, 2] else 100-tline.nsScore
            bucketNames = ['All Hands']   # everything goes in here
            if tline.decl is None:
                bucketNames.append('Passout or Avg')
            else:
                declIdx = 'NESW'.index(tline.decl)
                bucketNames.extend(bucketNameMap[(declIdx - playerIdx) % 4])
                # break down by games, partscores, slams
                offDefStr = 'Off' if 'Offense All' in bucketNames else 'Def'
                (level, suit) = tline.contract
                level = int(level)
                if ((suit in 'N'  and level >= 3) or
                    (suit in 'SH' and level >= 4) or
                    (suit in 'DC' and level >= 5)):
                    gameStr = 'Game/Slam'
                else:
                    gameStr = 'Partscore'
                bucketNames.append(f'{offDefStr} {gameStr}')
                bucketNames.append(f'All {gameStr}')

            # append oppName buckets
            oppNames = f'vs. {tline.playerDir[(playerIdx + 1) % 2]} + {tline.playerDir[(playerIdx + 1) % 2 + 2]}'
            bucketNames.append(oppNames)
            
            for bucketName in bucketNames:
                if not bucketTable[player][bucketName]:
                    bucketTable[player][bucketName] = Bucket()
                bucketTable[player][bucketName].add(score)
            # pprint(bucketTable)

def allScore(player):
    return bucketTable[player]['All Hands'].avg()

for player in sorted(bucketTable.keys(), reverse=True, key=allScore):
    partner = BboTravLineBase.origPartners[player]
    print(f'\n---------\n{player} & {partner}\n----------')
    # order of buckets shown
    displayList = [
        ('All Hands'     ,    'All Hands'),
        ('All Game/Slam' ,    '  All Game/Slam'),
        ('All Partscore' ,    '  All Partscore'),
        ('Passout or Avg',    '  Passout or Avg'),
        ('Offense All'   ,    '    Offense All'),
        ('OffDecl'       ,   f'      Declarer {player}'),
        ('OffDummy'      ,   f'      Declarer {partner}'),
        ('Defense All'   ,    '    Defense All'),
        ('DefLead'       ,   f'      Leader {player}'),
        ('DefNotLead'    ,   f'      Leader {partner}'),
        ]
        
    for (bucketName, displayName) in displayList:
        if args.debug:
            print(player, bucketName)
        if bucketName in bucketTable[player].keys():
            bucketTable[player][bucketName].show(displayName)

    print()
    # this uses player from the current scope
    def vsScore(bucketName):
        return bucketTable[player][bucketName].avg()
    
    for bucketName in sorted(bucketTable[player].keys(), reverse=True, key=vsScore):
        if bucketName.startswith('vs.'):
            bucketTable[player][bucketName].show(f'  {bucketName}', showCount=False)
            
