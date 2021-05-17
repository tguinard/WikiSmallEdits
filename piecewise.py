import re
import mwparserfromhell
from collections import Counter
import sys
import xml.etree.ElementTree as ET


class DoChunkCache:
    def __init__(self):
        self.cache = {}
    def dochunk(self, text, reftext, ida, idb, settings):
        def strip_prefixes(text, otherpieces):
            i = 0
            shared = []
            for piece in otherpieces:
                if piece.endswith('\n\n') and piece == text[i:i+len(piece)]:
                    shared.append(piece)
                    i = i + len(piece)
                else:
                    break
            return shared, text[i:]

        if ida in self.cache:
            pass
        elif idb in self.cache:
            otherpieces = self.cache[idb]
            prefixes, remaining1 = strip_prefixes(text, otherpieces)
            self.cache[ida] = prefixes + dochunk(remaining1, settings)
        else:
            self.cache[ida] = dochunk(text, settings)

        return self.cache[ida]

def iscomplete(html):
    return html.endswith('/>')

def isend(html):
    return html in '}]' or html.startswith('</')
    
def name(html):
    if html in '[]':
        return '[]'
    if html in '{}':
        return '{}'
    return re.search('\w+', html).group(0)

def allowedbreaks(tags, enters):
    stack = []
    ok = []
    start = 0
    for taginfo in tags:
        tag = taginfo.group(0)
        myname = name(tag)
        if myname != 'br':
       
            if len(stack) == 0:
                ok.append((start, taginfo.span()[0])) 
        
            if iscomplete(tag):
                pass
            elif isend(tag):
                if len(stack) and stack[-1] == myname:
                    stack.pop()
                else:
                    stack.append("INVALID!")
            else: #isstart
                stack.append(myname)
                
            if len(stack) == 0:
                start = taginfo.span()[1]
                
    if len(stack) == 0:
        ok.append((start, 10**20))
    else:
        ok.append((10**20, 10**20))
    oki = 0
    for enter in enters:
        index = enter.span()[0]
        while ok[oki][1] < index:
            oki += 1
        start, end = ok[oki]
        if start < index < end:
            yield enter
    
def referenceIndex(text, settings):
    result = re.search("(^|\n\n) *=* *" + settings.references + " *=* *\n", text)
    if result is None:
        return float('inf')
    return result.span()[0]
    
def spans(breaks, text, settings, noreferences=False):
    refi = float('inf')
    if noreferences:
        refi = referenceIndex(text, settings)
    breaks = list(breaks)
    starts = [0] + [b.span()[1] for b in breaks]
    ends = [b.span()[1] for b in breaks] + [-1]
    chunked = []
    for start, end in zip(starts, ends):
        if start >= refi:
            break
        if end < 0:
            chunked.append(text[start:])
        else:
            chunked.append(text[start:end])
    return chunked
    
def dochunk(text, settings):
    htmltags = list(re.finditer(r'(<[^<>]*\w[^<>]*>)|[][{}]', text))
    doubleenters = list(re.finditer('\n\n', text))
    breaks = allowedbreaks(htmltags, doubleenters)
    return spans(breaks, text, settings, True)
    
