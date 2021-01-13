from bbobase import BboBase
from bbotime import GridGen
import sys

class FakeArgs:
    def __init__(self):
        self.avoidUnsafeHtml = False

def htmlOpen():
    print(f'''
<!DOCTYPE html>
<html>
    <head>
	<style>
          {GridGen.styleInfo()}
	</style>
    </head>
  <body>
    ''')

def htmlClose():
    print('''
  </body>
</html>
    ''')



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
             ('tomato', 50, 0), ]
body += gridGen.gridRow('Long Waiter', roundData, '300+25', '40')

roundData = []
for n in range(100):
    roundData.append(('yellow', 0, 1))
body += gridGen.gridRow('WaitCells Only', roundData, '100+0', '40')
    
body += GridGen.divClose() + '\n'

print(body)

htmlClose()
