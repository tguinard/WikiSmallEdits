import re
import bz2
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher, Match
import sys
import json
from collections import defaultdict
import mwparserfromhell
from piecewise import dochunk, DoChunkCache
import os


def normalizeWord(word):
    if '|' in word:
        return word.split('|')[-1]
    return word
    
def contexttail(s, end):
    global settings
    cand = ' '.join(s[max(0, end-settings.maxcontext):end])
    newline = cand.rfind('\n') + 1
    newline2 = cand.rfind('\r') + 1
    p1 = cand.rfind('. ')
    p2 = cand.rfind('. ', 0, p1)
    return cand[max(0, p2, newline2, newline):]

def contexthead(s, start):
    cand = ' '.join(s[start:start+settings.maxcontext])
    newline = cand.find('\n')
    newline2 = cand.find('\r')
    p1 = cand.find('. ')
    p2 = cand.find('. ', p1, len(cand))
    return cand[:min([i for i in [len(cand), p2, newline2, newline] if i >= 0])]

def matches2edits(matches, before, after):
    global settings
    changes = []
    for m1, m2 in zip(matches, matches[1:]):
        alen = m2.a - m1.size - m1.a
        blen = m2.b - m1.size - m1.b
        adiff = ' '.join(before[m1.a + m1.size:m2.a])
        bdiff = ' '.join(after[m1.b + m1.size:m2.b])
        if alen <= settings.maxchange and blen <= settings.maxchange and re.search('\\w', adiff+bdiff) and ('\n' not in adiff+bdiff):
            change = {
                'a': adiff,
                'b': bdiff,
                'a1': contexttail(before, m1.a+m1.size) + ' ',
                'a2': ' ' + contexthead(before, m2.a),
                'b1': contexttail(after, m1.b+m1.size) + ' ',
                'b2': ' ' + contexthead(after, m2.b)
                }
            yield change

def tokenize(text):
    lines = text.split('\n')
    toks = []
    for line in lines:
        toks.extend(line.split())
        toks.append('\n')
    return toks

class Version:
    def __init__(self, parent, text):
        self.parent = parent
        self.text = text
        self.processed = False

def nonblank(lines):
    return [line for line in lines if len(line) > 20]

class LineBlocker: 
    def __init__(self, a, b, cache=None, ida=None, idb=None):
        global settings
        if cache is None:
            self.alines = dochunk(a, settings)
            self.blines = dochunk(b, settings)
        else:
            self.alines = cache.dochunk(a, b, ida, idb, settings)
            self.blines = cache.dochunk(b, a, idb, ida, settings)

        self.lineblocks = self._lineblocks()

    def _alignline(self):
        global settings
        acont = [p[:settings.contchar] for p in self.alines]
        bcont = [p[:settings.contchar] for p in self.blines]
        return SequenceMatcher(None, acont, bcont).get_matching_blocks()

    def _lineblocks(self):
        aligned = self._alignline()
        blocks = []
        first = aligned[0]
        if first.a != 0 or first.b != 0:
            blocks.append(('\n\n'.join(self.alines[0:first.a]), '\n\n'.join(self.blines[0:first.b])))
        for match, nextmatch in zip(aligned, aligned[1:]):
            for i in range(match.size-1):
                blocks.append((self.alines[match.a+i], self.blines[match.b+i]))
            blocks.append(('\n\n'.join(self.alines[match.a+match.size:nextmatch.a]), '\n\n'.join(self.blines[match.b+match.size:nextmatch.b])))
        return blocks

def versiontrees(xmllines):
    curlines = []
    collecting = False
    for line in xmllines:
        if line == '    <revision>\n' or line == '<revision>':
            collecting = True
        if collecting:
            curlines.append(line)
        if line == '    </revision>\n' or line == '</revision>':
            collecting = False
            if curlines[0][-1] == '\n':
                yield ET.fromstring(''.join(curlines))
            else:
                yield ET.fromstring('\n'.join(curlines))
            curlines = []


def process(xmllines):
    versions = {}
    edits = []
    page = {
        'title': xmllines[1].strip(),
        'ns': xmllines[2].strip(),
        'id': xmllines[3].strip()
        }
    for rev in versiontrees(xmllines):
        pid = rev.find('parentid')
        if pid is not None:
            pid = str(pid.text)
        myid = str(rev.find('id').text)
        t = str(rev.find('text').text or '')
        versions[myid] = Version(pid, t)
    
    cache = DoChunkCache()
    pcache = ParseCache()
    for myid, ver in versions.items():
        if ver.parent:
            beforenode = versions.get(ver.parent)
            before = beforenode.text if beforenode else ''
            after = ver.text
            edits.extend(textdiff(before, after, cache, ver.parent, myid, pcache))
    page["edits"] = edits
    return page
    
    
def normalizeWord(word):
    if '|' in word:
        return word.split('|')[-1]
    return word

def clean(text):
    global settings
    paragraphs = text.split('\n')
    newps = []
    for para in paragraphs:
        if para.strip() == settings.references:
            break
        para = ' '.join(normalizeWord(word) for word in para.split())
        newps.append(para)
    return '\n'.join(newps)
    
def markupToText(text):
    return clean(mwparserfromhell.parse(text).strip_code())
    
class ParseCache:
    def __init__(self):
        self.cache = {}
    def parse(self, text):
        if text not in self.cache:
            self.cache[text] = markupToText(text)
        return self.cache[text]

def textdiff(before, after, cache=None, id1=None, id2=None, parsecache=None):
    edits = [] 
    for atext, btext in LineBlocker(before, after, cache, id1, id2).lineblocks:
        if atext != btext:
            if parsecache:
                a = tokenize(parsecache.parse(atext))
                b = tokenize(parsecache.parse(btext))
            else:
                a = tokenize(markupToText(atext))
                b = tokenize(markupToText(btext))
            matches = SequenceMatcher(None, a, b).get_matching_blocks()
            edits.extend(matches2edits(matches, a, b))
    return edits

def process_long(f, toolong_file):
    collecting = False
    collectingrevision = False
    i = 0
    dependencies = {}
    title = None
    pageid = None
    parentid = None
    revisionid = None
    contributeOn = False
    for ln, line in enumerate(open(toolong_file, encoding='utf-8')):
        line = line.strip()
        if line == '<page>':
            i += 1
            print('reading', i, ln)
            title = None
            pageid = None
            collecting = True
        if collecting:
            if line == '<contributor>': contributeOn = True
            if line == '</contributor>': contributeOn = False
            if title is None and line.startswith('<title>'):
                title = line.split('>')[1].split('<')[0]
            if pageid is None and line.startswith('<id>'):
                pageid = line.split('>')[1].split('<')[0]
                dependencies[pageid] = defaultdict(set)

            if line == '<revision>':
                collectingrevision = True
                parentid = None
                revisionid = None
            if collectingrevision:
                if line.startswith('<id>') and not contributeOn:
                    revisionid = line.split('>')[1].split('<')[0]
                if line.startswith('<parentid>'):
                    parentid = line.split('>')[1].split('<')[0]
            if line == '</revision>':
                dependencies[pageid][parentid].add(revisionid)
                collectingrevision = False
        if line == '</page>':
            collecting = False
    curlines = []
    versions = {}
    chunkcache = DoChunkCache()
    parsecache = ParseCache()
    i = 0
    for ln, line in enumerate(open(toolong_file, encoding='utf-8')):
        line = line.strip()
        if line == '<page>':
            i += 1
            print('reading', i, ln)
            title = None
            pageid = None
            versions = {}
            edits = []
            collecting = True
            mydependencies = None
        if collecting:
            if line == '<contributor>': contributeOn = True
            if line == '</contributor>': contributeOn = False
            if title is None and line.startswith('<title>'):
                title = line.split('>')[1].split('<')[0]
            if pageid is None and line.startswith('<id>'):
                pageid = line.split('>')[1].split('<')[0]
                mydependencies = dependencies[pageid]

            if line == '<revision>':
                collectingrevision = True
                curlines = []

            if collectingrevision:
                curlines.append(line)

            if line == '</revision>':
                rev = ET.fromstring(''.join(curlines))
                pid = rev.find('parentid')
                if pid is not None:
                    pid = str(pid.text)
                myid = str(rev.find('id').text)
                t = str(rev.find('text').text or '')
                versions[myid] = Version(pid, t)
                if pid is None:
                    versions[myid].processed = True
                elif pid in versions:
                    versions[myid].processed = True
                    edits.extend(textdiff(versions[pid].text, versions[myid].text, chunkcache, pid, myid, parsecache))
                    mydependencies[pid].remove(myid)
                    if len(mydependencies[pid]) == 0 and versions[pid].processed:
                        del mydependencies[pid]
                        if chunkcache is not None:
                            del chunkcache.cache[pid]
                        del versions[pid]
                collectingrevision = False
        if line == '</page>':
            print('processing', i, ln)
            for myid, ver in versions.items():
                if not ver.processed:
                    pid = ver.parent
                    if pid and pid in versions:
                        edits.extend(textdiff(versions[pid].text, versions[myid].text, chunkcache, pid, myid))
            page = {'title': title, 'id': pageid, 'edits': edits}
            print(json.dumps(page), file=f)
            collecting = False

class Settings:
    def __init__(self, filename='settings.json'):
        obj = json.loads(open(filename).read())
        self.references = obj['references']
        self.maxchange = obj['maxchange']
        self.contchar = obj['contchar']
        self.maxcontext = obj['maxcontext']

if __name__ == '__main__':
    infile = sys.argv[1]
    outfile = sys.argv[2]
    
    settings = Settings()

    toolong = outfile + ".toolong"
    with open(outfile, 'w', encoding='utf-8') as f:
        with open(toolong, 'w', encoding='utf-8') as g:
            collecting = False
            istoolong = False
            curlines = []
            i = 0
            for ln, line in enumerate(bz2.open(infile)):
                line = line.decode("utf-8") 
                if line == '  <page>\n':
                    i += 1
                    print('reading', i, ln)
                    collecting = True
                    istoolong = False
                if collecting:
                    curlines.append(line)
                    if len(curlines) > 2000000:
                        istoolong = True
                if istoolong:
                    print(*curlines, file=g)
                    curlines = []
                if line == '  </page>\n' and not istoolong:
                    print('processing', i, ln)
                    collecting = False
                    page = process(curlines)
                    print(json.dumps(page), file=f)
                    curlines = []
        process_long(f, toolong)
    os.remove(toolong)