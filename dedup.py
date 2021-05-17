from os import listdir
import json
import re
from collections import Counter, defaultdict
import sys
import os


uniqid = 0
def contextkey(edit):
    global uniqid
    keep = 5
    
    prev = edit["b1"].split()[-keep:]
    nextt = edit["b2"].split()[:keep]
    if len(prev) + len(nextt) < keep:
        uniqid += 1
        return uniqid
    return (' '.join(prev), ' '.join(nextt))
    
def reduceContextKeyGroup(editseq):
    cur = editseq[-1]['b']
    #if it is a[0], everything is junk
    if editseq[0]['a'] == cur:
        return []
    for edit in editseq:
        if edit['b'] == cur:
            return [edit]
    
if __name__ == '__main__':
    folder = sys.argv[1]
    outfolder = sys.argv[2]
    if not os.path.isdir(outfolder):
        os.mkdir(outfolder)
        
    for f in listdir(folder):
        print('file', f)
        with open(outfolder + '/' + f, 'w') as outfile:
            for line in open(folder + '/' + f):
                page = json.loads(line)
                editsbycontext = defaultdict(list)
                if type(page) == dict:
                    for edit in page["edits"]:
                        editsbycontext[contextkey(edit)].append(edit)
                newedits = []
                for k, v in editsbycontext.items():
                    newedits.extend(reduceContextKeyGroup(v))
                page['edits'] = newedits
                print(json.dumps(page), file=outfile)
        