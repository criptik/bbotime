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
	     grid-template-rows: repeat(2, 1fr);
	     grid-gap: 1px;
	     padding: 2px;
	     background-color: grey;
	 }

	 .grid-container > div {
	     text-align: center;
	     padding: 5px 0;
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


def attrStr(attr, val):
    return f'{attr}="{val}"'

def divOpen(cls=None, styles=None, finalcr=True):
    classStr =  styleStr = ''
    if cls is not None:
        classStr = attrStr('class', cls)
    if styles is not None:
        stylist = ''
        for sty in styles.keys():
            stylist += f'{sty}:{styles[sty]}; '
        styleStr = attrStr('style', stylist)
    divStr = f'<div {classStr} {styleStr}>'
    if finalcr:
        divStr += '\n'
    return divStr

def divClose():
    return '</div>'

def divFull(cls=None, styles=None, content=''):
    return f'{divOpen(cls, styles, False)}{content}{divClose()}\n'


def textCellDiv(content):
    styles={}
    styles['grid-column-end'] = 'span 1'
    return divFull('divtext', styles, content)

def fullRowHtml(pairName, colorSpans, tots, max):
    nameCellStyles = {
        'background-color': 'white',
        'whitespace': 'nowrap',
        'padding-left': '5px',
        'padding-right': '5px',
        'grid-area': ' / 1 / / span 1',
    }
    s = ''
    s += divFull('divtext', nameCellStyles, pairName)
    for (color, spanAmt) in colorSpans:
        styles = {}
        styles['background-color'] = color
        styles['grid-column-end'] = f'span {spanAmt}'
        s += divFull(None, styles, f'{spanAmt}')
    for content in [tots, max]:
        s += textCellDiv(content)
    return s



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

body = '<p> Grid Example </p>'
body += divOpen('grid-container', {'grid-template-columns': 'repeat(103, 1fr)', 'width' : '1500px'})

colorSpans = [('cyan', 19),
              ('white', 1),
              ('yellow', 30),
              ('tomato', 50), ]
body += fullRowHtml('Really Really Long Pair Name', colorSpans, '100+25', '20')

colorSpans = [('cyan', 19),
              ('white', 1),
              ('yellow', 29),
              ('white', 1),
              ('tomato', 50), ]
body += fullRowHtml('Not So Long Pair Name', colorSpans, '200+25', '30')

colorSpans = [('cyan', 20),
              ('yellow', 30),
              ('white', 1),
              ('tomato', 49), ]

body += fullRowHtml('Short Pair Name', colorSpans, '300+25', '40')
body += divClose() + '\n'

print(body)

htmlClose()
