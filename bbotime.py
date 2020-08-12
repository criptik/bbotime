from bs4 import BeautifulSoup
import sys
import json
import time

# stuff that will become an arg
numbds = 21 
bpr = 3     # boards per round

map = {}

def readTime(str):
    return time.mktime(time.strptime(str, '%Y-%m-%d %H:%M'))

class TravLine(object):
    def __init__(self, bdnum, row):
        self.bdnum = bdnum
        self.iEndTime = readTime(row['Time'])
        self.north = row['North']
        self.east = row['East']
        self.waitMins = 0
        self.addStartTime()
        
    def addStartTime(self):
        if self.bdnum == 1:
            self.iStartTime = readTime('2020-08-07 15:00')
        else:
            prevTrav = map['%d-%s' % (self.bdnum-1, self.north)]
            prevTravOpp = map['%d-%s' % (self.bdnum-1, self.east)]
            ourPrevEnd =  prevTrav.iEndTime
            oppPrevEnd =  prevTravOpp.iEndTime
            if self.bdnum % bpr != 1:
                # use endtime of previous board
                # unless prev board was in a different round
                self.iStartTime = ourPrevEnd
            else:
                self.iStartTime = max(ourPrevEnd, oppPrevEnd)
                # and in this case compute wait time for prevTrav
                prevTrav.waitMins = (self.iStartTime - ourPrevEnd) / 60
                
    def showtime(self, itime):
        return(time.strftime('%H:%M', time.localtime(itime)))

    def __str__(self):
        mystr = ('N:%15s, E:%15s, Start:%5s, End:%5s, Elapsed:%2d' % (self.north, self.east,
                                                               self.showtime(self.iStartTime),
                                                               self.showtime(self.iEndTime),
                                                               (self.iEndTime - self.iStartTime)/60))
        if self.waitMins != 0:
            mystr = '%s, WaitMins:%2d' % (mystr, self.waitMins)
        return mystr

def addToMaps(bdnum, row):
    nkey = '%d-%s' % (bdnum, row['North'])
    ekey = '%d-%s' % (bdnum, row['East'])
    tline = TravLine(bdnum, row)
    map[nkey] = tline
    map[ekey] = tline


def printMap():
    for n in range(1, numbds+1):
        for k in sorted(map.keys()):
            if k.startswith('%d-' % (n)) and map[k].north in k:
                print(n, map[k])
        

def parseFile(n):
    # file = open('/home/tom/Downloads/hands (%d).html' % (n))
    file = open('./travs/T%d.html' % (n))
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

    print('---- Handling Traveller for Board %d ----' % (n))
    if False and n == 19:
        print(table_data)
        
    # place rows in big table indexed by boardnumber and North
    for row in table_data:
        addToMaps(n, row)


#-------- main stuff starts here -----------

for n in range(1,22):
    parseFile(n)
    
printMap()
# print(map['1-criptik']['Time'])
sys.exit(1)
