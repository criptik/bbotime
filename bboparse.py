from bs4 import BeautifulSoup
import json
import os

def parseFile(n, args):
    # two different naming options supported
    fname1 = f'{args.dir}/hands ({n}).html'
    fname2 = f'{args.dir}/T{n}.html'
    fname = fname1 if os.path.isfile(fname1) else fname2
    file = open(fname)
    html_doc = file.read()

    if args.debug:
        print(f'---- Handling Traveller File {fname} for Board {n} ----')
        

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
    return table_data

# builds list of tuples of bdnum and table_data (array of trav rows for that bdnum)
def readAllTravFiles(args):
    travTableData = []
    for bdnum in range(1, args.boards+1):
        table_data = parseFile(bdnum, args)
        travTableData.append((bdnum, table_data))
    return travTableData
