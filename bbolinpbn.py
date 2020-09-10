import re
import sys
sys.path.append('/home/tom/bridge/python-dds/examples')

import dds
import ctypes
import functions



# routines for converting lin to pbn
# here is a typical linstr:
# hv_popuplin('pn|jcgiordano,Snowball86,jagiordano,Ozzy43|st%7C%7Cmd%7C3S238JHKD4578JC37A%2CS5TAH368TD9TC56JQ%2CS7KH457QAD3QKAC4T%2C%7Crh%7C%7Cah%7CBoard%201%7Csv%7Co%7Cmb%7C1H%7Cmb%7Cp%7Cmb%7C1S%7Cmb%7Cp%7Cmb%7C2N%7Cmb%7Cp%7Cmb%7C3N%7Cmb%7Cp%7Cmb%7Cp%7Cmb%7Cp%7Cpc%7CC8%7Cpc%7CCA%7Cpc%7CC6%7Cpc%7CC4%7Cpc%7CHK%7Cpc%7CH3%7Cpc%7CH4%7Cpc%7CH2%7Cpc%7CD4%7Cpc%7CDT%7Cpc%7CDA%7Cpc%7CD2%7Cpc%7CDK%7Cpc%7CD6%7Cpc%7CD5%7Cpc%7CD9%7Cpc%7CDQ%7Cpc%7CC2%7Cpc%7CD7%7Cpc%7CS5%7Cpc%7CHA%7Cpc%7CH9%7Cpc%7CC3%7Cpc%7CH6%7Cpc%7CHQ%7Cpc%7CHJ%7Cpc%7CC7%7Cpc%7CH8%7Cpc%7CD3%7Cpc%7CS4%7Cpc%7CDJ%7Cpc%7CST%7Cpc%7CD8%7Cpc%7CC5%7Cpc%7CCT%7Cpc%7CS6%7Cpc%7CS2%7Cpc%7CSA%7Cpc%7CS7%7Cpc%7CS9%7Cpc%7CHT%7Cpc%7CH5%7Cpc%7CC9%7Cpc%7CS3%7Cpc%7CCQ%7Cpc%7CH7%7Cpc%7CCK%7Cpc%7CS8%7Cpc%7CSQ%7Cpc%7CSJ%7Cpc%7CCJ%7Cpc%7CSK%7C');this.style.color='red';return false;


# Here is a  typical pbn string
#     "N:QJ6.K652.J85.T98 873.J97.AT764.Q4 K5.T83.KQ9.A7652 AT942.AQ4.32.KJ3"


testStrings = ["hv_popuplin('pn|jcgiordano,Snowball86,jagiordano,Ozzy43|st%7C%7Cmd%7C3S238JHKD4578JC37A%2CS5TAH368TD9TC56JQ%2CS7KH457QAD3QKAC4T%2C%7Crh%7C%7Cah%7CBoard%201%7Csv%7Co%7Cmb%7C1H%7Cmb%7Cp%7Cmb%7C1S%7Cmb%7Cp%7Cmb%7C2N%7Cmb%7Cp%7Cmb%7C3N%7Cmb%7Cp%7Cmb%7Cp%7Cmb%7Cp%7Cpc%7CC8%7Cpc%7CCA%7Cpc%7CC6%7Cpc%7CC4%7Cpc%7CHK%7Cpc%7CH3%7Cpc%7CH4%7Cpc%7CH2%7Cpc%7CD4%7Cpc%7CDT%7Cpc%7CDA%7Cpc%7CD2%7Cpc%7CDK%7Cpc%7CD6%7Cpc%7CD5%7Cpc%7CD9%7Cpc%7CDQ%7Cpc%7CC2%7Cpc%7CD7%7Cpc%7CS5%7Cpc%7CHA%7Cpc%7CH9%7Cpc%7CC3%7Cpc%7CH6%7Cpc%7CHQ%7Cpc%7CHJ%7Cpc%7CC7%7Cpc%7CH8%7Cpc%7CD3%7Cpc%7CS4%7Cpc%7CDJ%7Cpc%7CST%7Cpc%7CD8%7Cpc%7CC5%7Cpc%7CCT%7Cpc%7CS6%7Cpc%7CS2%7Cpc%7CSA%7Cpc%7CS7%7Cpc%7CS9%7Cpc%7CHT%7Cpc%7CH5%7Cpc%7CC9%7Cpc%7CS3%7Cpc%7CCQ%7Cpc%7CH7%7Cpc%7CCK%7Cpc%7CS8%7Cpc%7CSQ%7Cpc%7CSJ%7Cpc%7CCJ%7Cpc%7CSK%7C');this.style.color='red';return false;",
               "hv_popuplin('pn|HCBS,rukh,Phog1,criptik|st%7C%7Cmd%7C3S56TH23789D4C256K%2CS4JAHD26JQKAC8JQA%2CS389KH46TAD3789C4%2C%7Crh%7C%7Cah%7CBoard%205%7Csv%7Cn%7Cmb%7Cp%7Cmb%7Cp%7Cmb%7Cp%7Cmb%7C2C%7Can%7Cforcing%3B%204%20or%20fewer%20losers%20or%2022%2B%20HCP%20Balanced%7Cmb%7Cp%7Cmb%7C2D%7Can%7Cat%20least%201%20A%20or%20K%7Cmb%7Cp%7Cmb%7C3D%7Cmb%7Cp%7Cmb%7C3H%7Cmb%7Cp%7Cmb%7C4C%7Cmb%7Cp%7Cmb%7C5C%7Cmb%7Cp%7Cmb%7C6C%7Cmb%7Cp%7Cmb%7Cp%7Cmb%7Cp%7Cpc%7CHA%7Cpc%7CH5%7Cpc%7CH2%7Cpc%7CC8%7Cpc%7CCA%7Cpc%7CC4%7Cpc%7CC3%7Cpc%7CC2%7Cpc%7CD2%7Cpc%7CD7%7Cpc%7CDT%7Cpc%7CD4%7Cpc%7CHK%7Cpc%7CH3%7Cpc%7CS4%7Cpc%7CH4%7Cpc%7CHQ%7Cpc%7CH7%7Cpc%7CSJ%7Cpc%7CH6%7Cpc%7CC7%7Cpc%7CC5%7Cpc%7CCQ%7Cpc%7CHT%7Cpc%7CCJ%7Cpc%7CS3%7Cpc%7CC9%7Cpc%7CCK%7Cpc%7CS5%7Cpc%7CSA%7Cpc%7CS8%7Cpc%7CS2%7Cpc%7CDA%7Cpc%7CD3%7Cpc%7CD5%7Cpc%7CC6%7Cpc%7CS6%7Cpc%7CD6%7Cpc%7CSK%7Cpc%7CS7%7Cpc%7CS9%7Cpc%7CSQ%7Cpc%7CST%7Cpc%7CDJ%7Cpc%7CHJ%7Cpc%7CH8%7Cpc%7CDQ%7Cpc%7CD8%7Cpc%7CCT%7Cpc%7CH9%7Cpc%7CDK%7Cpc%7CD9%7C');this.style.color='red';return false;"
               ]

def cardRank(c):
    return '23456789TJQKA'.index(c)
    

class Hand(object):
    def __init__(self):
        self.suits = []

    @classmethod
    def fromPbnHandStr(cls, handstr):
        newHand = cls()
        for suitstr in handstr.split('.'):
            newHand.suits.append(set(suitstr))
        return newHand

    @classmethod
    def fromSuitSets(cls, suitsets):
        newHand = cls()
        for suitset in suitsets:
            newHand.suits.append(suitset)
        return newHand

    @classmethod
    def allCards(cls):
        newHand = cls()
        for n in range(4):
            newHand.suits.append(set('23456789TJQKA'))
        return newHand

    def toPbnString(self):
        result = ''
        for suit in self.suits:
            if result != '':
                result = result + '.'
            result = result + ''.join(sorted(suit, reverse=True, key=cardRank))
        return result
    
    def __str__(self):
        result = ''
        for s in self.suits:
            result = result + f'{s} '
        return result

class Deal(object):
    # a set of 4 hands
    def __init__(self, hands):
        self.hands = hands
        if len(hands) == 3:
            # fill in missing hand
            missHand = Hand.allCards()

            for hand in self.hands:
                for (i, suitset) in enumerate(hand.suits):
                    missHand.suits[i] = missHand.suits[i] - suitset

            self.hands.append(missHand)



    def toPbnString(self):
        result = 'S:'
        for (i, hand) in enumerate(self.hands):
            if i != 0:
                result = result + ' '
            result = result + hand.toPbnString()
        return result
    
        
for str in testStrings:
    str = re.sub('%7C', '|', str)
    str = re.sub('%2C', ' ', str)
    str = re.sub('^.*md\|\d', '', str)
    str = re.sub('\|rh\|.*$', '', str)
    str = re.sub('S', ' ', str)
    str = re.sub('[HDC]', '.', str)
    str = str.lstrip(' ')
    str = str.rstrip(' ')
    str3Hands = str.split('  ')
    print(str3Hands)

    hands = []
    for handstr in str3Hands:
        hands.append(Hand.fromPbnHandStr(handstr))

    mydeal = Deal(hands)
    
    # now build missing hand
    if False:
        for hand in hands:
            print(hand)

    pbnResult = Deal(hands).toPbnString()
    print('dealpbn= ', pbnResult)

    DDdealsPBN = dds.ddTableDealsPBN()
    tableRes = dds.ddTablesRes()
    pres = dds.allParResults()
    pres2 = dds.parResultsDealer()

    mode = 0
    tFilter = ctypes.c_int * dds.DDS_STRAINS
    trumpFilter = tFilter(0, 0, 0, 0, 0)
    line = ctypes.create_string_buffer(80)

    dds.SetMaxThreads(0)

    DDdealsPBN.noOfTables = 1
    DDdealsPBN.deals[0].cards = pbnResult.encode('utf-8')
    res = dds.CalcAllTablesPBN(ctypes.pointer(DDdealsPBN), mode, trumpFilter, ctypes.pointer(tableRes), ctypes.pointer(pres))
    functions.PrintPBNHand('Hand', DDdealsPBN.deals[0].cards)

    print('Table\n-------')
    functions.PrintTable(ctypes.pointer(tableRes.results[0]))

    dlrVulMap = {
        1: (0, 0),
        2: (1, 2),
        3: (2, 3),
        4: (3, 1),
        5: (0, 2),
        6: (1, 3),
        7: (2, 1),
        8: (3, 0),
        9: (0, 3),
        10: (1, 1),
        11: (2, 0),
        12: (3, 2),
        13: (0, 1),
        14: (1, 0),
        15: (2, 2),
        16: (3, 3),
}
    for bdnum in range(1,5):
        print(f'bdnum = {bdnum}')
        (dlr, vul) = dlrVulMap[bdnum]
        res = dds.DealerPar(ctypes.pointer(tableRes.results[0]), ctypes.pointer(pres2), dlr, vul)
        functions.PrintDealerPar(ctypes.pointer(pres2))    
