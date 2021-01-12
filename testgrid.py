from bbobase import BboBase
import sys

class FakeArgs:
    def __init__(self):
        self.avoidUnsafeHtml = False

def htmlOpen():
    print('''
<!DOCTYPE html>
<html>
    <head>
	<style>
	 .grid-container {
	     display: grid;
	     grid-gap: 1px;
	     padding: 2px;
	     background-color: grey;
	 }

	 .grid-container > div {
	     text-align: center;
	     padding-top: 5px;
	     padding-bottom: 5px;
	     font-size: 15px;
             max-height: 25px;
	 }

         .divtext {
             background-color: white;
             white-space: nowrap;
             padding-left: 5px;
             padding-right: 5px
          }

         table, th, td {
        	 border: 1px solid black;
                 border-collapse: collapse;
         }

	 table {
	     table-layout: auto;
	     width: 1500px;
             font-size: 20px;
	 }

	</style>
    </head>
  <body>
    ''')

def htmlClose():
    print('''
  </body>
</html>
    ''')



class GridGen(object):
    def __init__(self, rowTime):
        self.rowTime = rowTime
        self.rowNum = 1
        
    def gridOpen(self):
        # +3 here because of name, tot, max columns
        colTemplate = f'repeat({3 + self.rowTime}, 1fr)'
        return self.divOpen('grid-container', {'grid-template-columns': colTemplate, 'width' : '1500px'})

    def gridRow(self, pairName, roundData, tots, max):
        # basically checks the roundData meets rowTime
        totalTime = 0
        colorSpans = []
        for (color, playTime, waitTime) in roundData:
            colorSpans.append((color, playTime))
            colorSpans.append(('white', waitTime))
            totalTime += (playTime + waitTime)
        if totalTime != self.rowTime:
            print(f'row {self.rowNum}, roundData does not add up to {self.rowTime}: {roundData}', file=sys.stderr)
            if totalTime <= self.rowTime:
                waitDelta = self.rowTime - totalTime
                print(f'adding waitTime of {waitDelta} at the end', file=sys.stderr)
                (color, oldWaitTime) = colorSpans.pop()
                colorSpans.append((color, oldWaitTime + waitDelta))
            else:
                # greater than, no fixup possible
                print(f'Fatal', file=sys.stderr)
                sys.exit(1)
        self.rowNum += 1
        return self.fullRowHtml(pairName, colorSpans, tots, max)

    @staticmethod
    def attrStr(attr, val):
        return f'{attr}="{val}"'

    @staticmethod
    def divOpen(cls=None, styles=None, finalcr=True):
        classStr =  styleStr = ''
        if cls is not None:
            classStr = GridGen.attrStr('class', cls)
        if styles is not None:
            stylist = ''
            for sty in styles.keys():
                stylist += f'{sty}:{styles[sty]}; '
            styleStr = GridGen.attrStr('style', stylist)
        divStr = f'<div {classStr} {styleStr}>'
        if finalcr:
            divStr += '\n'
        return divStr

    @staticmethod
    def divClose():
        return '</div>'

    @staticmethod
    def divFull(cls=None, styles=None, content=''):
        return f'{GridGen.divOpen(cls, styles, False)}{content}{GridGen.divClose()}\n'


    @staticmethod
    def textCellDiv(content):
        styles={}
        styles['grid-column-end'] = 'span 1'
        return GridGen.divFull('divtext', styles, content)

    @staticmethod
    def fullRowHtml(pairName, colorSpans, tots, max):
        nameCellStyles = {
            'grid-area': ' / 1 / / span 1',
        }
        s = ''
        s += GridGen.divFull('divtext', nameCellStyles, pairName)
        for (color, spanAmt) in colorSpans:
            if spanAmt == 0:
                continue
            styles = {}
            styles['background-color'] = color
            styles['grid-column-end'] = f'span {spanAmt}'
            s += GridGen.divFull(None, styles, f'{spanAmt}')
        for content in [tots, max]:
            s += GridGen.textCellDiv(content)
        return s + '\n'

#----- main starts here ----------
if False:
    sdict = {
    'grid-area': '  / 1 /  / span 1'
    }
    print(divFull('divtext', sdict, 'Really Really Long Pair Name'))
    sys.exit(1)
    
args = FakeArgs()
htmlOpen()
numcols = 4
numrows = 4

body = '<p> Grid Example </p>\n'
gridGen = GridGen(100)

body += gridGen.gridOpen()

roundData = [('cyan', 19, 1),
             ('yellow', 30, 0),
             ('tomato', 50,  0)]
body += gridGen.gridRow('Really Really Long Pair Name', roundData, '100+25', '20')

roundData = [('cyan', 19, 1),
             ('yellow', 28, 3),
             ('tomato', 49, 0)]
body += gridGen.gridRow('Not So Long Pair Name', roundData, '200+25', '30')

roundData = [('cyan', 20, 0),
             ('yellow', 30, 2),
             ('tomato', 48, 0), ]

body += gridGen.gridRow('Short Pair Name', roundData, '300+25', '40')

roundData = [('cyan', 10, 0),
             ('yellow', 15, 25),
             ('tomato', 70, 0), ]
body += gridGen.gridRow('Long Waiter', roundData, '300+25', '40')

roundData = []
for n in range(100):
    roundData.append(('yellow', 0, 1))
body += gridGen.gridRow('WaitCells Only', roundData, '100+0', '40')
    
body += GridGen.divClose() + '\n'

print(body)

htmlClose()
