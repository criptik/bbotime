import sys
import time
import os
import itertools
from pprint import pprint
import bboparse

gibName = 'GiB'
vsstr = ' vs. '
robotData = {}


class BboRobotFixer(object):
    def __init__(self, args, travTableData):
        self.args = args
        self.travTableData = travTableData
        self.initRobotData()
    
    
    # this routine is called if robotScores are supplied,
    # use those to try to differentiate between two or more robot pairs
    def robotFix(self):
        #first check that all supplied robot scores are unique, otherwise we can't deduce anything
        if len(set(self.args.robotScores)) != len(self.args.robotScores):
            print('Error: Robot Scores must all be unique')
            sys.exit(1)

        for bdnum in range (1, self.args.boards + 1):
            # place rows in big table indexed by boardnumber and North and East names
            for row in self.travTableData[bdnum]:
                self.buildRobotData(bdnum, row)

        if self.args.debug:
            print('----- snapshot of robotData ----')
            print(robotData)

        # this maps a robot score to a list of possible keysets
        # ideally this maps to 1 (0 or >1 would be an error)
        robScoreKeyLists = {}
        for robscore in self.args.robotScores:
            robScoreKeyLists[robscore] = []

        allLegalKeylists = self.getAllLegalRobotKeylists()
        for keylist in allLegalKeylists:
            totScore = self.getScoreAllBoards(keylist)
            # now see if it matches any total robotScores
            # and put it in robScoreKeyLists if it does
            for robscore in self.args.robotScores:
                if totScore == robscore:
                    robScoreKeyLists[robscore].append(keylist)

        # now check that each robscore does appear exactly once in the robScoreKeyLists
        # Note: on success need to eventually go back thru self.travTableData and change GiB names
        errorExit = False
        for robscore in self.args.robotScores:
            keylistArray = robScoreKeyLists[robscore]
            if len(keylistArray) == 0:
                print(f'Error: no keylists combos match for robot score {robscore}')
                errorExit = True
            elif len(keylistArray) > 1:
                # see if we have a special case where we can just pick one of two
                chosenKeylist = self.checkKeylistDiffs(keylistArray, robscore)
                if chosenKeylist is not None:
                    self.fixRobotNamesInTravs(robscore, chosenKeylist)
                else:
                    print(f'Error: multiple keylists combos match for robot score {robscore}')
                    for keylist in keylistArray:
                        pprint(keylist)
                    errorExit = True
            else:
                # exactly one entry in the list
                # fix up the robotnames to be unique
                self.fixRobotNamesInTravs(robscore, keylistArray[0])
        if errorExit:
            sys.exit(1)


    def initRobotData(self):
        for rndnum in range(1, int(self.args.boards/self.args.bpr) + 1):
            robotData[rndnum] = {}


    def addRobotScores(self, bdnum, row, dir):
        # robotData will be keyed by roundnum and oppName
        # and the direction which helps if robot is playing robot
        rndnum = int((bdnum-1)/self.args.bpr) + 1
        oppdir = 'East' if dir == 'North' else 'North'
        key = f'{dir}{vsstr}{row[oppdir].lower()}'
        if robotData[rndnum].get(key) == None:
            robotData[rndnum][key] = []
        # add the score
        fscore = float(row['Score'][:-1])  # strip % sign off end
        if dir == 'East':
            fscore = 100.0 - fscore
        robotData[rndnum][key].append(fscore)
        # print(bdnum, dir, robotData)

    def buildRobotData(self, bdnum, row):
        # only do this if one of the two pairs is a robot pair
        for dir in ['North', 'East']:
            if row[dir] == gibName and row[bboparse.partnerDir[dir]] == gibName:
                self.addRobotScores(bdnum, row, dir)

    def robKeyOppNamesUnique(self, keylist):
        oppMap = {}
        for key in keylist:
            oppname = key.split(vsstr)[1]
            if oppMap.get(oppname) is None:
                oppMap[oppname] = 1
            else:
                return False
        # if we get this far, success
        return True

    def getAllLegalRobotKeylists(self):
        # use itertools to get all the combinations
        keysets = []
        for rndnum in range(1, int(self.args.boards/self.args.bpr) + 1):
            keysets.append(list(robotData[rndnum].keys()))
        if self.args.debug:
            pprint(keysets)

        allCombos = list(itertools.product(*keysets))
        allLegalKeylists = []
        for keylist in allCombos:
            # first make sure all the opponent names are unique across rounds
            # and if so, combine all the scores for all rounds into one list so we can avg it
            if self.robKeyOppNamesUnique(keylist):    
                allLegalKeylists.append(keylist)
        return allLegalKeylists

    def getScoreAllBoards(self, keylist):
        # for this keylist, combine all the scores for all rounds into one list so we can avg it
        rndnum = 1
        scores = []
        for key in keylist:
            scores.extend(robotData[rndnum][key])
            rndnum += 1
        avg = round(sum(scores) / len(scores), 2)
        return avg

    def fixRobotNamesInTravs(self, robscore, keylist):
        print('robscore=', robscore)
        pprint(keylist)
        rndnum = 1    
        for key in keylist:
            for bdnum in range(((rndnum-1) * self.args.bpr) + 1, (rndnum * self.args.bpr) + 1):
                table_data = self.travTableData[bdnum]
                # find the row that has robotName in expected direction
                # and playing expected opp
                (direction, oppname) = key.split(vsstr)
                oppdir = 'East' if direction == 'North' else 'North'
                rowsChanged = 0
                if self.args.debug:
                    print(f'bdnum {bdnum}, {robscore}, {key}')
                for row in table_data:
                    # todo: make this more robust if players start with the same substring
                    if row[direction].startswith(gibName) and row[oppdir].lower().startswith(oppname):
                        row[direction] = f'{gibName}-{robscore}'
                        parddir = bboparse.partnerDir[direction]
                        row[parddir] = f'{gibName}-{robscore}-pard'
                        rowsChanged += 1
                        if self.args.debug:
                            print(f'after: {rowsChanged} ', end='')
                            pprint(row)
                assert(rowsChanged == 1)
            rndnum += 1

    def checkKeylistDiffs(self, keylistArray, robscore):
        if len(keylistArray) > 2:
            return None
        # see if only differ in one key
        (keylist1, keylist2) = keylistArray
        numDiffs = 0
        for (key1, key2) in zip(keylist1, keylist2):
            if key1 != key2:
                numDiffs += 1
                (dir1, opp1) = key1.split(vsstr)
                (dir2, opp2) = key2.split(vsstr)
                if opp1 == 'gib' and opp2 == 'gib':
                    # difference is resolvable, return one based on our position
                    # in the self.args.robotScores array
                    scorepos = self.args.robotScores.index(robscore)
                    candidate = keylistArray[scorepos]
        if numDiffs == 1:
            print('picked keylist which differed insignificantly')
            return candidate
        else:
            return None

