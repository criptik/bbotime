import sys
import time
import os
import collections
import sys
import time
import os
import collections
from pprint import pprint

from bbobase import BboBase, BboTravLineBase, Bucket

def nested_dict():
    return collections.defaultdict(nested_dict)


class BboStatsReporter(BboBase):
    def appDescription(self):
        return 'BBO Tourney Defense/Offense Analysis'

    def addParserArgs(self, parser):
        pass

    def childGenReport(self):
        map = {}
        players = {}
        partners = {}
        opps = {}
        bucketTable = nested_dict()
        vsOppTable = nested_dict()
      
        bucketNameMap = [
            ['OffDecl',    'Offense All'],      # 0
            ['DefNotLead', 'Defense All'],      # 1
            ['OffDummy',   'Offense All'],      # 2
            ['DefLead',    'Defense All'],      # 3
        ]

        def allScore(player):
            return bucketTable[player]['All Hands'].avg()

        BboStatsTravLine.importArgs(self.args)
        for bdnum in range (1, self.args.boards + 1):
            for row in self.travTableData[bdnum]:
                tline = BboStatsTravLine(bdnum, row, self.travParser)
                # print(f'bdnum={bdnum}')
                # pprint(tline.__dict__)
                # for now, we really only need North and East
                for player in tline.playerDir[:2]:
                    playerIdx = tline.playerDir.index(player)
                    pard = tline.playerDir[(playerIdx+2)%4]
                    # if names are specified check whether player or his partner are in names, skip if not
                    if self.args.names is not None and player not in self.args.names and pard not in self.args.names:
                        continue
                    score = tline.nsScore if playerIdx in [0, 2] else 100-tline.nsScore
                    bucketNames = ['All Hands']   # everything goes in here
                    # for interim scores add it to the appropriate 'thru' buckets
                    round = int((bdnum-1)/self.args.bpr) + 1
                    totalRounds = int(self.args.boards / self.args.bpr)
                    for n in range(round, totalRounds+1):
                        bucketNames.append(f'Thru Round {n:2}')
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
                if self.args.debug:
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

            print()
            for bucketName in sorted(bucketTable[player].keys()):
                if bucketName.startswith('Thru '):
                    bucketTable[player][bucketName].show(f'  {bucketName}', showCount=False)
                    
        
class BboStatsTravLine(BboTravLineBase):
    def __init__(self, bdnum, row, travParser):
        super(BboStatsTravLine, self).__init__(bdnum, row, travParser)
        # nothing added here

#-------- main stuff starts here -----------

BboStatsReporter().genReport()

