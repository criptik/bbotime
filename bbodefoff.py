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

bigTable = nested_dict()

class Bucket(object):
    def __init__(self):
        self.ary = []
        
    def show(self, bucketName):
        bucketList = bigTable[player][bucketName]
        listlen = len(self.ary)
        avg = round(sum(self.ary) / listlen, 2)
        prefix = '' if bucketName == 'All' else ' ' if bucketName.endswith('All') else '  '
        alignedName = prefix + bucketName
        print(f'{alignedName:<15} {avg:5.2f} ({listlen})')

    def add(self, score):
        self.ary.append(score)            

#-------- main stuff starts here -----------

myBboParser = BboDefOffParser()
args = myBboParser.parseArguments()
if args.debug:
    print(args.__dict__)

travTableData = []
#read all traveler files into travTableData
travTableData = myBboParser.readAllTravFiles()

bucketNameMap = [
    ['OffDecl',    'OffAll'],      # 0
    ['DefNotLead', 'DefAll'],      # 1
    ['OffDummy',   'OffAll'],      # 2
    ['DefLead',    'DefAll'],      # 3
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
            bucketNames = ['All']   # catch-all
            if tline.decl is None:
                bucketNames = ['Passout or Avg']
            else:
                declIdx = 'NESW'.index(tline.decl)
                bucketNames.extend(bucketNameMap[(declIdx - playerIdx) % 4])
                # break down by games, partscores, slams
                offDefStr = 'Off' if 'OffAll' in bucketNames else 'Def'
                (level, suit) = tline.contract
                level = int(level)
                if (level >= 6):
                    gameStr = 'Slam'
                elif ((suit in 'N'  and level >= 3) or
                      (suit in 'SH' and level >= 4) or
                      (suit in 'DC' and level >= 5)):
                    gameStr = 'Game'
                else:
                    gameStr = 'Partscore'
                bucketNames.append(f'{offDefStr} {gameStr}')
            
                    
            oppNames = f'vs. {tline.playerDir[(playerIdx + 1) % 2]} + {tline.playerDir[(playerIdx + 1) % 2 + 2]}'
            bucketNames.append(oppNames)
            
            for bucketName in bucketNames:
                if not bigTable[player][bucketName]:
                    bigTable[player][bucketName] = Bucket()
                bigTable[player][bucketName].add(score)
            # pprint(bigTable)
            
for player in bigTable.keys():
    print(f'\n---------\n{player}')
    for bucketName in sorted(bigTable[player].keys()):
        bigTable[player][bucketName].show(bucketName)

# pprint(bigTable)
