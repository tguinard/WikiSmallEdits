# Split the big edit history *.bz2 file into multiple files that don't split up pages
# Usage: splitBz2.py edit_history_dump.bz2 outputDirectory/

import bz2
import sys
import os

bigbz2filename = sys.argv[1]
outdir = sys.argv[2]
if not os.path.isdir(outdir):
    os.mkdir(outdir)
    
template = outdir + "/%s.bz2"

i = 0
f = bz2.open(template % i, "wb")
wanttoclose = False

for linenum, line in enumerate(bz2.open(bigbz2filename)):
    if linenum % 100000 == 0: print('Read up to line', linenum)
    f.write(line)
    if linenum > 1 and linenum % 50000000 == 0:
        wanttoclose = True
    if wanttoclose and line.decode('utf-8').strip() == '</page>':
        print(linenum, 'closing')
        i += 1
        f.close()
        f = bz2.open(template % i, "wb")
        wanttoclose = False
f.close()
