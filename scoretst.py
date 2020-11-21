import sys
def getVulIndex(bdnum):
    return [0,2,3,1,2,3,1,0,3,1,0,2,1,0,2,3][(bdnum-1) % 16]
        
# get raw score possible for a suit and level and double situation
# given that dd computed we can take trix number of tricks
def getRawScore(bdnum, suit, level, dblFlag, pair, trix):
    downDblNotVulList = (0, 100, 300, 500, 800, 1100, 1400, 1700, 2000, 2300, 2600, 2900, 3200, 3500)
    downDblVulList    = (0, 200, 500, 800, 1100, 1400, 1700, 2000, 2300, 2600, 2900, 3200, 3500, 3800)

    vulIndex = getVulIndex(bdnum)   # self.getVulIndex()
    isVul = vulIndex == 1 or (pair == 'NS' and vulIndex == 2) or (pair == 'EW' and vulIndex == 3)
    # print(suit, level+6, trix, file=sys.stderr)
    if trix < level+6:
        # going down
        down = (level+6) - trix
        if dblFlag == 0:
            score = down * 50 if not isVul else down * 100
        elif dblFlag == 1 or dblFlag == 2:
            downList = downDblNotVulList if not isVul else downDblVulList
            score = downList[down] * dblFlag
        return -1*score
    else:
        # making something
        gamebonus = 50
        slambonus = 0
        # making contract
        overtrix = (trix-6) - level
        ptsPerTrick = 20 if suit in 'DC' else 30
        trickOneBonus = 10 if suit == 'N' else 0
        bidTrickVal = trickOneBonus + level * ptsPerTrick * (2 ** dblFlag)
        if dblFlag == 0:
            overTrickVal = overtrix * ptsPerTrick
        else:
            overTrickVal = overtrix * (100 if not isVul else 200) * (dblFlag)
        if bidTrickVal >= 100:
            gamebonus = 300 if not isVul else 500
        if level == 6:
            slambonus = 500 if not isVul else 750
        elif level == 7:
            slambonus = 1000 if not isVul else 1500
        insultVal = 50 * dblFlag
        return bidTrickVal + overTrickVal + gamebonus + slambonus + insultVal
                    
for bdnum in range(1,5):
    for suit in 'CDHSN':
        for level in range(1,8):
            for dblFlag in range(0,3):
                for pair in ['NS', 'EW']:
                    for trix in range(7,14):
                        if trix < level+6:
                            continue
                        rawscore = getRawScore(bdnum, suit, level, dblFlag, pair, trix)
                        print(bdnum, suit, level, dblFlag, pair, trix, '------>', rawscore)
